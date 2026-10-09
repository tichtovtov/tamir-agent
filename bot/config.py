"""Runtime configuration, loaded from environment variables / .env.

Every tunable value lives here; other modules import `Config` instead of reading
the environment themselves. See .env.example for documentation of each variable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Fixed values (not meant to be changed per deployment)
RATES_API_URL = "https://open.er-api.com/v6/latest/USD"
RATES_BASE_CURRENCY = "USD"
ALLOWED_USERS_FILENAME = "allowed_users.json"
USER_PREFS_FILENAME = "user_prefs.json"
# A pending clarification is forgotten after this many seconds of silence
CONVERSATION_TTL_SECONDS = 600
# How many recent messages of a clarification exchange are sent to the language model
CONVERSATION_MAX_MESSAGES = 8


@dataclass(frozen=True)
class Config:
    """Validated bot configuration."""

    telegram_token: str
    admin_name: str
    default_currency: str
    ollama_url: str
    ollama_model: str
    ollama_text_model: str
    ollama_timeout: float
    data_dir: Path
    rates_ttl: int
    log_level: str

    @property
    def allowed_users_path(self) -> Path:
        return self.data_dir / ALLOWED_USERS_FILENAME

    @property
    def user_prefs_path(self) -> Path:
        return self.data_dir / USER_PREFS_FILENAME


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


def load_config() -> Config:
    """Load configuration from the environment (and .env if present).

    Raises:
        ConfigError: if TELEGRAM_BOT_TOKEN is missing or a numeric value is invalid.
    """
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and set the token "
            "you got from @BotFather."
        )

    try:
        ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT", "90"))
        rates_ttl = int(os.getenv("RATES_TTL", "3600"))
    except ValueError as e:
        raise ConfigError(f"Invalid numeric value in configuration: {e}") from e

    vision_model = os.getenv("OLLAMA_MODEL", "gemma3:12b")
    return Config(
        telegram_token=token,
        admin_name=os.getenv("ADMIN_NAME", "אלעד"),
        default_currency=os.getenv("DEFAULT_CURRENCY", "ILS").upper(),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=vision_model,
        ollama_text_model=os.getenv("OLLAMA_TEXT_MODEL") or vision_model,
        ollama_timeout=ollama_timeout,
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        rates_ttl=rates_ttl,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
