"""Telegram handlers: authorization gate, commands, text and photo messages.

Flow for every update:
1. `gate` (group -1) stops unauthorized users with a message containing their ID.
2. Commands (/start, /help, /set, /currency), text, photos, or the fallback handler.
Shared services are stored in `application.bot_data["services"]`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from bot import currencies, messages, parser
from bot.auth import AllowList
from bot.config import Config
from bot.parser import ParsedPrice
from bot.rates import RatesClient, RatesUnavailableError, UnknownCurrencyError
from bot.storage import UserPrefs
from bot.vision import OllamaVision, VisionUnavailableError

log = logging.getLogger(__name__)

# Arguments to /from that clear the default source currency
CLEAR_WORDS = {"off", "none", "clear", "ביטול", "בטל", "-"}


@dataclass
class Services:
    """Everything handlers need, created once at startup."""

    config: Config
    allow_list: AllowList
    prefs: UserPrefs
    rates: RatesClient
    vision: OllamaVision


def _services(context: ContextTypes.DEFAULT_TYPE) -> Services:
    return context.application.bot_data["services"]


async def _reply(update: Update, text: str) -> None:
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Block users who are not in allowed_users.json."""
    user = update.effective_user
    if user is None or update.effective_message is None:
        raise ApplicationHandlerStop
    s = _services(context)
    if s.allow_list.is_allowed(user.id):
        return
    log.info("Unauthorized user %s (%s)", user.id, user.full_name)
    await _reply(update, messages.unauthorized(user.id, s.config.admin_name))
    raise ApplicationHandlerStop


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start, /help and any unsupported input."""
    s = _services(context)
    uid = update.effective_user.id
    await _reply(
        update,
        messages.help_text(
            s.allow_list.name_of(uid), s.prefs.get_currency(uid), s.prefs.get_source(uid)
        ),
    )


async def _show_settings(update: Update, s: Services) -> None:
    uid = update.effective_user.id
    await _reply(
        update, messages.current_settings(s.prefs.get_currency(uid), s.prefs.get_source(uid))
    )


async def currency_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/currency: show the target and default source currencies."""
    await _show_settings(update, _services(context))


async def _validate_currency(update: Update, s: Services, token: str) -> str | None:
    """Return the ISO code for `token` if supported; otherwise reply with an error, return None."""
    code = currencies.normalize(token)
    try:
        supported = await s.rates.supported()
    except RatesUnavailableError:
        await _reply(update, messages.RATES_UNAVAILABLE)
        return None
    if code is None or code not in supported:
        await _reply(update, messages.unknown_currency(token))
        return None
    return code


async def set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/set <currency>: change the target currency."""
    s = _services(context)
    user = update.effective_user
    if not context.args:
        await _show_settings(update, s)
        return
    code = await _validate_currency(update, s, " ".join(context.args))
    if code is None:
        return
    s.prefs.set_currency(user.id, code, user.full_name)
    log.info("User %s set currency to %s", user.id, code)
    await _reply(update, messages.currency_set(code))


async def from_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/from <currency>: default source currency for bare numbers; /from off clears it."""
    s = _services(context)
    user = update.effective_user
    if not context.args:
        await _show_settings(update, s)
        return
    token = " ".join(context.args)
    if token.strip().lower() in CLEAR_WORDS:
        s.prefs.set_source(user.id, None, user.full_name)
        log.info("User %s cleared source currency", user.id)
        await _reply(update, messages.SOURCE_CLEARED)
        return
    code = await _validate_currency(update, s, token)
    if code is None:
        return
    s.prefs.set_source(user.id, code, user.full_name)
    log.info("User %s set source currency to %s", user.id, code)
    await _reply(update, messages.source_set(code))


async def _convert_and_reply(update: Update, s: Services, price: ParsedPrice) -> None:
    uid = update.effective_user.id
    target = s.prefs.get_currency(uid)
    try:
        conv = await s.rates.convert(price.amount, price.currency, target)
    except UnknownCurrencyError as e:
        await _reply(update, messages.unknown_currency(e.code))
        return
    except RatesUnavailableError:
        log.exception("Rates unavailable")
        await _reply(update, messages.RATES_UNAVAILABLE)
        return
    log.info("User %s: %s %s -> %.2f %s", uid, price.amount, price.currency, conv.result, target)
    await _reply(update, messages.conversion(conv))


async def text_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Free text: parse a price, or show help."""
    s = _services(context)
    price = parser.parse(update.effective_message.text)
    uid = update.effective_user.id
    log.info("User %s text -> %s", uid, price)
    if price is None:
        await help_cmd(update, context)
        return
    # A bare number uses the user's default source currency (set with /from)
    currency = price.currency or s.prefs.get_source(uid)
    if currency is None:
        await _reply(update, messages.missing_currency(price.amount))
    else:
        await _convert_and_reply(update, s, ParsedPrice(price.amount, currency))


async def photo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Photo (or image file): read the price with the vision model."""
    s = _services(context)
    msg = update.effective_message
    await msg.chat.send_action(ChatAction.TYPING)

    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    image = bytes(await (await context.bot.get_file(file_id)).download_as_bytearray())

    try:
        price = await s.vision.extract_price(image)
    except VisionUnavailableError:
        log.exception("Vision model unavailable")
        await _reply(update, messages.VISION_UNAVAILABLE)
        return
    log.info("User %s photo -> %s", update.effective_user.id, price)

    if price is None:
        await _reply(update, messages.NO_PRICE_IN_IMAGE)
        return
    # Priority: currency in the caption > currency seen in the image > user's /from default
    caption_code = currencies.normalize(msg.caption) if msg.caption else None
    currency = caption_code or price.currency or s.prefs.get_source(update.effective_user.id)
    if currency is None:
        await _reply(update, messages.image_missing_currency(price.amount))
        return
    await _convert_and_reply(update, s, ParsedPrice(price.amount, currency))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unexpected errors and tell the user something went wrong."""
    log.exception("Unhandled error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("😕 משהו השתבש. נסו שוב.")


def register(app: Application) -> None:
    """Attach all handlers to the application."""
    app.add_handler(TypeHandler(Update, gate), group=-1)
    app.add_handler(CommandHandler(["start", "help"], help_cmd))
    app.add_handler(CommandHandler("set", set_cmd))
    app.add_handler(CommandHandler("from", from_cmd))
    app.add_handler(CommandHandler("currency", currency_cmd))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo_msg))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_msg))
    # Anything else (stickers, voice, unknown commands...) gets the help text
    app.add_handler(MessageHandler(filters.ALL, help_cmd))
    app.add_error_handler(error_handler)
