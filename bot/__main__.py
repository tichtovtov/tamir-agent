"""Entry point: `python -m bot`.

Loads configuration, runs startup checks (data dir, allow-list, Ollama), then
starts the bot in long-polling mode (no public URL needed).
"""

from __future__ import annotations

import asyncio
import logging
import sys

from telegram import BotCommand
from telegram.ext import Application

from bot import __version__, handlers
from bot.auth import AllowList
from bot.config import Config, ConfigError, load_config
from bot.rates import RatesClient
from bot.storage import UserPrefs
from bot.vision import OllamaVision

log = logging.getLogger("bot")

COMMANDS = [
    BotCommand("set", "קביעת מטבע היעד, למשל /set USD"),
    BotCommand("from", "מטבע מקור למספר בלי מטבע, למשל /from EUR"),
    BotCommand("currencies", "רשימת מטבעות והקודים שלהם"),
    BotCommand("currency", "הצגת ההגדרות הנוכחיות"),
    BotCommand("help", "איך משתמשים בבוט"),
]


def _check_data_dir(config: Config) -> None:
    """Make sure the data directory exists and is writable; warn if the allow-list is missing."""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    probe = config.data_dir / ".write_test"
    try:
        probe.write_text("ok")
        probe.unlink()
    except OSError as e:
        raise ConfigError(f"Data directory {config.data_dir} is not writable: {e}") from e
    if not config.allowed_users_path.exists():
        log.warning(
            "%s not found — nobody can use the bot yet. "
            "Create it (see data/allowed_users.example.json).",
            config.allowed_users_path,
        )


async def _post_init(app: Application) -> None:
    services: handlers.Services = app.bot_data["services"]
    problem = await services.vision.check()
    if problem:
        # Text conversions still work; only photos fail. Warn loudly instead of exiting.
        log.warning("Image recognition unavailable: %s", problem)
    else:
        log.info("Ollama OK (model %s)", services.config.ollama_model)
    await app.bot.set_my_commands(COMMANDS)


async def _post_shutdown(app: Application) -> None:
    services: handlers.Services = app.bot_data["services"]
    await services.rates.aclose()
    await services.vision.aclose()


def main() -> int:
    try:
        config = load_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # httpx logs every request (including the bot token in the URL) at INFO
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        _check_data_dir(config)
    except ConfigError as e:
        log.error("%s", e)
        return 1

    app = (
        Application.builder()
        .token(config.telegram_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.bot_data["services"] = handlers.Services(
        config=config,
        allow_list=AllowList(config.allowed_users_path),
        prefs=UserPrefs(config.user_prefs_path, config.default_currency),
        rates=RatesClient(config.rates_ttl),
        vision=OllamaVision(config.ollama_url, config.ollama_model, config.ollama_timeout),
    )
    handlers.register(app)

    log.info("Starting bot v%s (default currency %s)", __version__, config.default_currency)
    app.run_polling()
    return 0


if __name__ == "__main__":
    # Python 3.12+ no longer creates a default event loop; PTB's run_polling expects one
    asyncio.set_event_loop(asyncio.new_event_loop())
    sys.exit(main())
