"""Telegram handlers: authorization gate, commands, text and photo messages.

Flow for every update:
1. `gate` (group -1) stops unauthorized users with a message containing their ID.
2. Commands (/start, /help, /set, /from, /currency, /currencies), currency-button
   presses, text, photos, or the fallback handler.
Shared services are stored in `application.bot_data["services"]`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from bot import catalog, currencies, messages, parser
from bot.auth import AllowList
from bot.config import Config
from bot.parser import ParsedPrice
from bot.rates import RatesClient, RatesUnavailableError, UnknownCurrencyError
from bot.storage import UserPrefs
from bot.vision import OllamaVision, VisionUnavailableError

log = logging.getLogger(__name__)

# /set changes the target currency, /from the default source currency
KIND_SET, KIND_FROM = "set", "from"
# Arguments to /from that clear the default source currency
CLEAR_WORDS = {"off", "none", "clear", "ביטול", "בטל", "-"}
BUTTONS_PER_ROW = 4
MAX_MATCH_BUTTONS = 12


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


async def _reply(update: Update, text: str, keyboard: InlineKeyboardMarkup | None = None) -> None:
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


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


def _keyboard(kind: str, codes: list[str], with_clear: bool = False) -> InlineKeyboardMarkup:
    """Buttons (4 per row) whose callback data is "<kind>:<code>", e.g. "from:VND"."""
    buttons = [
        InlineKeyboardButton(
            catalog.BY_CODE[c].label() if c in catalog.BY_CODE else c,
            callback_data=f"{kind}:{c}",
        )
        for c in codes
    ]
    rows = [buttons[i : i + BUTTONS_PER_ROW] for i in range(0, len(buttons), BUTTONS_PER_ROW)]
    if with_clear:
        rows.append([InlineKeyboardButton("❌ ביטול מטבע המקור", callback_data=f"{kind}:off")])
    return InlineKeyboardMarkup(rows)


def _apply(s: Services, user: User, kind: str, code: str | None) -> str:
    """Save the choice and return the confirmation text. code=None clears the source."""
    if kind == KIND_SET:
        s.prefs.set_currency(user.id, code, user.full_name)
        log.info("User %s set currency to %s", user.id, code)
        return messages.currency_set(code)
    s.prefs.set_source(user.id, code, user.full_name)
    log.info("User %s set source currency to %s", user.id, code)
    return messages.source_set(code) if code else messages.SOURCE_CLEARED


async def _resolve(s: Services, token: str) -> list[str]:
    """Supported currency codes matching a code, symbol, alias, name or country.

    Raises:
        RatesUnavailableError: if the list of supported currencies cannot be fetched.
    """
    supported = await s.rates.supported()
    code = currencies.normalize(token)
    if code in supported:
        return [code]
    return [c.code for c in catalog.search(token) if c.code in supported]


async def _choose_currency(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> None:
    """Shared logic of /set and /from: buttons, direct match, or a pick among several matches."""
    s = _services(context)
    user = update.effective_user
    if not context.args:
        with_clear = kind == KIND_FROM and s.prefs.get_source(user.id) is not None
        await _reply(
            update,
            messages.choose_currency(kind),
            _keyboard(kind, list(catalog.POPULAR), with_clear),
        )
        return

    token = " ".join(context.args)
    if kind == KIND_FROM and token.strip().lower() in CLEAR_WORDS:
        await _reply(update, _apply(s, user, kind, None))
        return
    try:
        codes = await _resolve(s, token)
    except RatesUnavailableError:
        await _reply(update, messages.RATES_UNAVAILABLE)
        return
    if not codes:
        await _reply(update, messages.unknown_currency(token))
    elif len(codes) == 1:
        await _reply(update, _apply(s, user, kind, codes[0]))
    else:
        await _reply(
            update, messages.multiple_matches(token), _keyboard(kind, codes[:MAX_MATCH_BUTTONS])
        )


async def set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/set [currency]: change the target currency."""
    await _choose_currency(update, context, KIND_SET)


async def from_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/from [currency]: default source currency for bare numbers; /from off clears it."""
    await _choose_currency(update, context, KIND_FROM)


async def currency_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A press on a currency button from /set or /from."""
    s = _services(context)
    query = update.callback_query
    kind, _, value = query.data.partition(":")
    code = None if value == "off" and kind == KIND_FROM else value
    if code is not None:
        try:
            supported = await s.rates.supported()
        except RatesUnavailableError:
            await query.answer(messages.RATES_UNAVAILABLE, show_alert=True)
            return
        if code not in supported:
            await query.answer()
            return
    text = _apply(s, update.effective_user, kind, code)
    await query.answer()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)


async def currencies_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/currencies: list of common currencies with codes."""
    await _reply(update, messages.currency_list())


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
    app.add_handler(CommandHandler("currencies", currencies_cmd))
    app.add_handler(CallbackQueryHandler(currency_button, pattern=r"^(set|from):"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo_msg))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_msg))
    # Anything else (stickers, voice, unknown commands...) gets the help text
    app.add_handler(MessageHandler(filters.ALL, help_cmd))
    app.add_error_handler(error_handler)
