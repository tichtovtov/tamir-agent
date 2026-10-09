# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and versions follow [SemVer](https://semver.org/).

## [Unreleased]

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
