# CLAUDE.md

Telegram currency-conversion bot (Python, python-telegram-bot, local Ollama vision). Architecture: `docs/ARCHITECTURE.md`.

## Commands
- `make setup`: venv + deps + `.env` / `data/allowed_users.json` if missing
- `make test` / `make lint` / `make format`
- `make run` (local) · `make docker-up` (Docker, Ollama on host)

## Conventions
- All config/env access and constants go through `bot/config.py`.
- All user-facing text lives in `bot/messages.py` (Hebrew, HTML parse mode; `html.escape` anything user-provided).
- Image recognition uses local Ollama only. Don't add cloud LLM/vision APIs.
- Bot never writes `data/allowed_users.json` (admin edits it by hand); per-user state goes in `user_prefs.json`.
- Module + public function docstrings, type hints, ruff-clean.
- Every change: add/adjust tests, update `CHANGELOG.md` (and README/ARCHITECTURE if behavior or setup changes).
- Pin new dependencies in `requirements.txt` / `requirements-dev.txt`.
