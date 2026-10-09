# Shortcuts for common tasks. Run `make help` for the list.
PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
MODEL ?= $(shell grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2)
MODEL := $(if $(MODEL),$(MODEL),qwen2.5vl:7b)

.PHONY: help setup model run test lint format docker-up docker-down docker-logs

help:  ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup:  ## Create venv, install deps, create .env and data files if missing
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -U pip
	$(BIN)/pip install -r requirements-dev.txt
	@test -f .env || (cp .env.example .env && echo ">> Created .env — fill in TELEGRAM_BOT_TOKEN")
	@test -f data/allowed_users.json || (echo '{}' > data/allowed_users.json && echo ">> Created empty data/allowed_users.json")

model:  ## Pull the Ollama vision model
	ollama pull $(MODEL)

run:  ## Run the bot locally
	$(BIN)/python -m bot

test:  ## Run tests
	$(BIN)/pytest -q

lint:  ## Check lint and formatting
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:  ## Auto-fix lint and formatting
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

docker-up:  ## Build and start the bot in Docker (background)
	docker compose up -d --build

docker-down:  ## Stop the Docker container
	docker compose down

docker-logs:  ## Follow the Docker container logs
	docker compose logs -f
