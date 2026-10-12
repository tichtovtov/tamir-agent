# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and versions follow [SemVer](https://semver.org/).

## [Unreleased]
### Added
- Magnitude suffixes in amounts: `k` / `אלף` (thousand), `m` / `מיליון` (million), `b` / `bn` / `מיליארד` (billion), e.g. `10k`, `$1.5m`, `2M ₪`, `5 אלף דולר`. Parsed directly by the regular parser (case-insensitive). Currency aliases such as `kr` and `kč` are not affected. The language-model prompt explains the suffixes too, as a fallback.

## [0.4.0] - 2026-10-09
### Added
- Free-text understanding with a local language model (Ollama): a message the regular parser doesn't recognize is interpreted by the model. That can be a conversion with a one-off target currency ("כמה זה 30 יורו בדולרים?"), a settings change ("אני טס ליפן"), clearing the source currency, help, or a **clarifying question** when something is missing or unclear.
- Conversation memory for clarifications: an answer to the bot's question (`יורו`, `50`) is understood in context. Kept in memory only, cleared after an action or after 10 minutes.
- Settings changes from free text are saved only after a confirmation button (✅ כן / ❌ לא).
- `OLLAMA_TEXT_MODEL` setting (default: same as `OLLAMA_MODEL`).
- `make model` also pulls the text model if it's different.
### Changed
- Default model is now `gemma3:12b` (instead of `qwen2.5vl:7b`): tested on both images and Hebrew text.
- Shared Ollama client (`bot/ollama.py`) for images and text; the startup check covers both models.
- Questions like "which currency?" (for a bare number or an image without a currency) are remembered, so the answer is understood in context.

## [0.3.0] - 2026-10-09
### Added
- `/currencies` command: a list of about 50 common currencies by region, with a flag, Hebrew name and code.
- Search for a currency by country or name in `/set` and `/from` (`/from וייטנאם`, `/set dong`, `/from פראג`). Several matches → selection buttons.
- `/set` and `/from` with no argument show quick-pick buttons for popular currencies (plus a cancel button in `/from`).
- Currency names in free text: `דונג`, `וון`, `יואן`, `רופיה`, `פורינט`, `לארי`, `dong`, `won`, `forint`, and more.
### Changed
- Confirmations and `/currency` show the full currency name with a flag (e.g. 🇻🇳 דונג וייטנאמי (VND)).

## [0.2.0] - 2026-10-09
### Added
- `/from <currency>` command: a default source currency, saved per user in `user_prefs.json` (`source` field). A bare number, or an image with no currency, is converted from it. Handy for trips. `/from off` cancels.
- Handler tests (`tests/test_handlers.py`).
### Changed
- `/currency` and the help message show the default source currency too.

## [0.1.0] - 2026-10-09
### Added
- Telegram bot that converts prices from text (`100 USD`, `€25`, `50 יורו`) into each user's target currency.
- Reading prices from price-tag images with a local vision model through Ollama (default `qwen2.5vl:7b`), with an option to give the currency in the caption.
- Commands: `/start`, `/help`, `/set <currency>`, `/currency`. Default target currency is ILS.
- Authorized-users list in `data/allowed_users.json` with automatic reload. An unauthorized user gets their ID.
- Exchange rates from open.er-api.com with a one-hour cache and a fallback to a stored rate.
- Startup check (token, data directory, Ollama and model).
- Local run (`make run`) and Docker run (`docker compose`) with Ollama on the host.
- Tests (pytest), lint (ruff), Makefile, and documentation (README, ARCHITECTURE, CLAUDE.md).
