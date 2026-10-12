"""Telegram handlers: authorization gate, commands, text and photo messages.

Flow for every update:
1. `gate` (group -1) stops unauthorized users with a message containing their ID.
   Admins (ADMIN_IDS) always pass.
2. Commands (/start, /help, /set, /from, /currency, /currencies), admin commands
   (/add_user, /remove_user, /users), button presses, text, photos, or the
   fallback handler.
Text that parser.py understands is converted directly; anything else goes to the
language model (nlu.py), which may lead to a conversion, a proposed settings change
(confirmed with a button), or a clarifying question.
Shared services are stored in `application.bot_data["services"]`.
"""

from __future__ import annotations

import html
import logging
import re
import time
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
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
from bot.config import CONVERSATION_MAX_MESSAGES, CONVERSATION_TTL_SECONDS, Config
from bot.nlu import Interpretation, OllamaNLU
from bot.ollama import OllamaClient, OllamaUnavailableError
from bot.parser import ParsedPrice
from bot.rates import RatesClient, RatesUnavailableError, UnknownCurrencyError
from bot.storage import BotUsers, UserPrefs
from bot.vision import OllamaVision

log = logging.getLogger(__name__)

# /set changes the target currency, /from the default source currency
KIND_SET, KIND_FROM = "set", "from"
# Arguments to /from that clear the default source currency
CLEAR_WORDS = {"off", "none", "clear", "ביטול", "בטל", "-"}
CANCEL = "cancel"  # callback data of the "no" button
CONVERSATION_KEY = "conversation"  # context.user_data key of the clarification memory
BUTTONS_PER_ROW = 4
MAX_MATCH_BUTTONS = 12


@dataclass
class Services:
    """Everything handlers need, created once at startup."""

    config: Config
    allow_list: AllowList
    bot_users: BotUsers
    prefs: UserPrefs
    rates: RatesClient
    ollama: OllamaClient
    vision: OllamaVision
    nlu: OllamaNLU


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
    if _is_admin(s, user.id) or s.allow_list.is_allowed(user.id):
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
            s.allow_list.name_of(uid),
            s.prefs.get_currency(uid),
            s.prefs.get_source(uid),
            is_admin=_is_admin(s, uid),
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
    name = s.allow_list.name_of(user.id)
    if kind == KIND_SET:
        s.prefs.set_currency(user.id, code, user.full_name)
        log.info("User %s set currency to %s", user.id, code)
        return messages.currency_set(code, name)
    s.prefs.set_source(user.id, code, user.full_name)
    log.info("User %s set source currency to %s", user.id, code)
    return messages.source_set(code, name) if code else messages.source_cleared(name)


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
    """A press on a currency/confirmation button ("set:USD", "from:off", "cancel")."""
    s = _services(context)
    query = update.callback_query
    _forget(context)
    if query.data == CANCEL:
        await query.answer()
        await query.edit_message_text(messages.CANCELLED)
        return
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


async def _convert_and_reply(
    update: Update, s: Services, price: ParsedPrice, target: str | None = None
) -> None:
    """Convert to `target` (default: the user's target currency) and reply."""
    uid = update.effective_user.id
    target = target or s.prefs.get_currency(uid)
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


# --- Clarification memory ---------------------------------------------------------
# While the bot waits for an answer to a question it asked, the exchange is kept in
# context.user_data (in memory only) so the language model can read the answer in
# context. It is cleared once a request is fulfilled, or expires after a while.


def _conversation(context: ContextTypes.DEFAULT_TYPE) -> list[dict]:
    """Messages of the pending clarification exchange (empty if none or expired)."""
    conv = context.user_data.get(CONVERSATION_KEY)
    if not conv or time.monotonic() - conv["ts"] > CONVERSATION_TTL_SECONDS:
        return []
    return conv["messages"]


def _forget(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(CONVERSATION_KEY, None)


async def _ask(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    question: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """Send a question and remember the exchange for the next message."""
    await _reply(update, question, keyboard)
    plain = html.unescape(re.sub(r"<[^>]+>", "", question))
    msgs = _conversation(context) + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": plain},
    ]
    context.user_data[CONVERSATION_KEY] = {
        "ts": time.monotonic(),
        "messages": msgs[-CONVERSATION_MAX_MESSAGES:],
    }


# --- Messages -------------------------------------------------------------------


async def text_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Free text: a clear price is converted directly; anything else goes to the language model."""
    s = _services(context)
    text = update.effective_message.text
    uid = update.effective_user.id
    price = parser.parse(text)
    log.info("User %s text -> %s", uid, price)

    # Not a price, or a bare number that may answer a pending question → language model
    if price is None or (price.currency is None and _conversation(context)):
        await _understand(update, context, text)
        return
    # A bare number uses the user's default source currency (set with /from)
    currency = price.currency or s.prefs.get_source(uid)
    if currency is None:
        await _ask(update, context, text, messages.missing_currency(price.amount))
        return
    _forget(context)
    await _convert_and_reply(update, s, ParsedPrice(price.amount, currency))


async def _understand(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Interpret free text with the language model and act on it (or ask a question)."""
    s = _services(context)
    uid = update.effective_user.id
    await update.effective_message.chat.send_action(ChatAction.TYPING)
    try:
        it = await s.nlu.interpret(
            text,
            _conversation(context),
            s.prefs.get_currency(uid),
            s.prefs.get_source(uid),
            messages.first_name(s.allow_list.name_of(uid)),
        )
    except OllamaUnavailableError:
        log.exception("Language model unavailable")
        _forget(context)
        await help_cmd(update, context)
        return
    log.info("User %s NLU -> %s", uid, it)

    try:
        if it.action == "convert":
            await _nlu_convert(update, context, text, it)
        elif it.action in ("set_target", "set_source"):
            kind = KIND_SET if it.action == "set_target" else KIND_FROM
            await _nlu_setting(update, context, text, kind, it)
        elif it.action == "clear_source":
            await _nlu_clear_source(update, context)
        elif it.action == "clarify":
            await _ask(update, context, text, messages.clarify(it.question))
        else:
            _forget(context)
            if it.action == "show_settings":
                await _show_settings(update, s)
            elif it.action == "list_currencies":
                await currencies_cmd(update, context)
            else:
                await help_cmd(update, context)
    except RatesUnavailableError:
        await _reply(update, messages.RATES_UNAVAILABLE)


async def _nlu_convert(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, it: Interpretation
) -> None:
    s = _services(context)
    if it.amount is None or it.amount <= 0:
        await _ask(update, context, text, messages.clarify(it.question))
        return
    if it.currency:
        codes = await _resolve(s, it.currency)
        if len(codes) != 1:
            await _ask(update, context, text, messages.which_currency(it.currency, codes))
            return
        currency = codes[0]
    else:
        currency = s.prefs.get_source(update.effective_user.id)
        if currency is None:
            await _ask(update, context, text, messages.missing_currency(it.amount))
            return
    # One-off target ("how much is it in euros"); ignored if it can't be resolved
    target = None
    if it.target_currency:
        targets = await _resolve(s, it.target_currency)
        target = targets[0] if len(targets) == 1 else None
    _forget(context)
    await _convert_and_reply(update, s, ParsedPrice(it.amount, currency), target)


async def _nlu_setting(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, kind: str, it: Interpretation
) -> None:
    """Propose a settings change understood from free text; applied only via a button."""
    s = _services(context)
    # Models sometimes put the currency of a set_target in target_currency; accept either
    token = it.currency or it.target_currency
    if not token:
        await _ask(update, context, text, messages.clarify(it.question))
        return
    codes = await _resolve(s, token)
    if not codes:
        await _ask(update, context, text, messages.which_currency(token, codes))
        return
    _forget(context)
    if len(codes) > 1:
        await _reply(
            update,
            messages.multiple_matches(token),
            _keyboard(kind, codes[:MAX_MATCH_BUTTONS]),
        )
        return
    await _reply(
        update,
        messages.confirm_setting(kind, codes[0], s.allow_list.name_of(update.effective_user.id)),
        _confirm_keyboard(f"{kind}:{codes[0]}"),
    )


async def _nlu_clear_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    s = _services(context)
    _forget(context)
    source = s.prefs.get_source(update.effective_user.id)
    if source is None:
        await _reply(update, messages.NO_SOURCE_SET)
        return
    await _reply(
        update,
        messages.confirm_clear_source(source, s.allow_list.name_of(update.effective_user.id)),
        _confirm_keyboard(f"{KIND_FROM}:off"),
    )


def _confirm_keyboard(yes_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(messages.YES_BUTTON, callback_data=yes_data),
                InlineKeyboardButton(messages.NO_BUTTON, callback_data=CANCEL),
            ]
        ]
    )


async def photo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Photo (or image file): read the price with the vision model."""
    s = _services(context)
    msg = update.effective_message
    await msg.chat.send_action(ChatAction.TYPING)

    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    image = bytes(await (await context.bot.get_file(file_id)).download_as_bytearray())

    try:
        price = await s.vision.extract_price(image)
    except OllamaUnavailableError:
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
        user_text = msg.caption or messages.PHOTO_PLACEHOLDER
        await _ask(update, context, user_text, messages.image_missing_currency(price.amount))
        return
    _forget(context)
    await _convert_and_reply(update, s, ParsedPrice(price.amount, currency))


# --- Admin commands (user management) -------------------------------------------
# Users added here go to bot_users.json; allowed_users.json is never written.
# For anyone who is not an admin these commands behave like an unknown command.


def _is_admin(s: Services, user_id: int) -> bool:
    return user_id in s.config.admin_ids


def _parse_user_id(raw: str) -> int | None:
    """A Telegram user ID from a command argument, or None if it isn't one."""
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


async def add_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/add_user <id> <name>: allow a user and notify them (admins only)."""
    s = _services(context)
    admin = update.effective_user
    if not _is_admin(s, admin.id):
        await help_cmd(update, context)
        return
    user_id = _parse_user_id(context.args[0]) if context.args else None
    if user_id is None:
        await _reply(update, messages.ADD_USER_USAGE)
        return
    if user_id in s.allow_list.manual_users():
        await _reply(update, messages.user_already_manual(user_id))
        return
    name = " ".join(context.args[1:]).strip()
    s.bot_users.add(user_id, name, added_by=admin.id)
    log.info("Admin %s added user %s (%s)", admin.id, user_id, name)
    try:
        await context.bot.send_message(
            user_id, messages.welcome_added(name), parse_mode=ParseMode.HTML
        )
        notified = True
    except TelegramError as e:
        log.info("Could not notify new user %s: %s", user_id, e)
        notified = False
    await _reply(update, messages.user_added(user_id, name, notified))


async def remove_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/remove_user <id>: remove a user added from Telegram (admins only)."""
    s = _services(context)
    admin = update.effective_user
    if not _is_admin(s, admin.id):
        await help_cmd(update, context)
        return
    user_id = _parse_user_id(context.args[0]) if context.args else None
    if user_id is None:
        await _reply(update, messages.REMOVE_USER_USAGE)
        return
    name = s.bot_users.all().get(user_id)
    if s.bot_users.remove(user_id):
        log.info("Admin %s removed user %s", admin.id, user_id)
        await _reply(update, messages.user_removed(user_id, name))
    elif user_id in s.allow_list.manual_users():
        await _reply(update, messages.user_remove_manual(user_id))
    else:
        await _reply(update, messages.user_not_found(user_id))


async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/users: list authorized users (admins only)."""
    s = _services(context)
    if not _is_admin(s, update.effective_user.id):
        await help_cmd(update, context)
        return
    await _reply(
        update,
        messages.users_list(s.allow_list.manual_users(), s.bot_users.all(), s.config.admin_ids),
    )


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
    app.add_handler(CommandHandler("add_user", add_user_cmd))
    app.add_handler(CommandHandler("remove_user", remove_user_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CallbackQueryHandler(currency_button, pattern=r"^((set|from):\w+|cancel)$"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo_msg))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_msg))
    # Anything else (stickers, voice, unknown commands...) gets the help text
    app.add_handler(MessageHandler(filters.ALL, help_cmd))
    app.add_error_handler(error_handler)
