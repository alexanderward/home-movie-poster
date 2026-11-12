PYTHON := uv run python
POSTER := uv run poster
PNPM := npx --yes pnpm@12.11.2 --dir apps/client
COMPOSE := docker compose --env-file .env -f docker/compose.yaml

.DEFAULT_GOAL := help

.PHONY: help setup start stop restart logs compose compose-check migrate manage web client monitor client-build client-contracts lint python-types test test-ui

help: ## Show the public command catalogue
	@$(PYTHON) scripts/commands.py list

setup: ## Install locked Python and client dependencies
	uv sync --locked
	$(PNPM) install --frozen-lockfile

start: ## Build and start the application
	$(COMPOSE) up --build --remove-orphans

stop: ## Stop the development stack
	$(COMPOSE) down

restart: ## Rebuild and recreate the application
	$(COMPOSE) down
	$(COMPOSE) up --build --remove-orphans

logs: ## Follow stack logs
	$(COMPOSE) logs --follow --tail=200

compose: ## Pass ARGS to Docker Compose
	$(COMPOSE) $(ARGS)

compose-check: ## Validate the Compose file
	docker compose --env-file .env.example -f docker/compose.yaml config --quiet

migrate: ## Apply Django database migrations
	$(POSTER) manage migrate --noinput

manage: ## Run a Django management command with ARGS
	$(POSTER) manage $(ARGS)

web: ## Run Django locally with reload
	$(POSTER) web --host 0.0.0.0 --port 8001 --reload

client: ## Run Vite locally
	$(PNPM) dev --host 0.0.0.0

monitor: ## Run Kaleidescape discovery natively
	$(POSTER) monitor

client-build: ## Type-check and build modern and legacy client bundles
	$(PNPM) build

client-contracts: ## Regenerate TypeScript contracts from Pydantic
	$(PYTHON) scripts/generate_contracts.py

lint: ## Run Python, client, import, and command lint checks
	uv run ruff check .
	uv run lint-imports
	$(PNPM) lint
	$(PYTHON) scripts/commands.py check

python-types: ## Run Pyright
	uv run pyright

test: ## Run fast Python and client tests
	uv run pytest
	$(PNPM) test

test-ui: ## Run Playwright browser journeys
	uv run pytest -m browser
