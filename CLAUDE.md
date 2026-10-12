# CLAUDE.md

Telegram currency-conversion bot (Python, python-telegram-bot, local Ollama vision). Architecture: `docs/ARCHITECTURE.md` (diagram version: `docs/ARCHITECTURE.html`).

## Commands
- `make setup`: venv + deps + `.env` / `data/allowed_users.json` if missing
- `make test` / `make lint` / `make format`
- `make run` (local) · `make docker-up` (Docker, Ollama on host)

## Conventions
- All config/env access and constants go through `bot/config.py`.
- Currency metadata: free-text aliases in `bot/currencies.py`, names/flags/countries for lists & search in `bot/catalog.py`.
- All user-facing text lives in `bot/messages.py` (Hebrew, HTML parse mode; `html.escape` anything user-provided).
- Image recognition and free-text understanding use local Ollama only (`bot/ollama.py`). Don't add cloud LLM/vision APIs.
- The language model only interprets (`bot/nlu.py`); handlers validate every currency, and settings changes need a confirmation button.
- Bot never writes `data/allowed_users.json` (admin edits it by hand); per-user state goes in `user_prefs.json`.
- Module + public function docstrings, type hints, ruff-clean.
- Every change: add/adjust tests, update `CHANGELOG.md` (and README/ARCHITECTURE if behavior or setup changes; `docs/ARCHITECTURE.md` and `docs/ARCHITECTURE.html` are kept in sync).
- Pin new dependencies in `requirements.txt` / `requirements-dev.txt`.
