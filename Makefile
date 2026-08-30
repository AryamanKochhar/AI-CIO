# AI-CIO — unified local development commands
SHELL := /bin/bash
COMPOSE := docker compose
ROOT := $(CURDIR)
PYTHON ?= python3
VENV := $(ROOT)/.venv
VENV_BIN := $(VENV)/bin
SERVICE ?=

.PHONY: install dev-up dev-down dev-restart dev-logs db-up db-down db-migrate db-reset test lint typecheck build clean help

help:
	@echo "AI-CIO development commands:"
	@echo "  make install      Install Python + pnpm dependencies and create .env if missing"
	@echo "  make dev-up       Start PostgreSQL, migrate, API, and web (one command)"
	@echo "  make dev-down     Stop the development stack (keeps database volume)"
	@echo "  make dev-restart  Restart the development stack"
	@echo "  make dev-logs     Follow logs (SERVICE=postgres|api|web optional)"
	@echo "  make db-up        Start only PostgreSQL"
	@echo "  make db-down      Stop only PostgreSQL"
	@echo "  make db-migrate   Run Alembic migrations against the dev database"
	@echo "  make db-reset     Destroy local dev database volume and recreate (destructive)"
	@echo "  make test         Run backend pytest suite"
	@echo "  make lint         Run frontend lint"
	@echo "  make typecheck    Run frontend typecheck"
	@echo "  make build        Build frontend apps"
	@echo "  make clean        Remove build artifacts and Python cache"

install: ensure-env
	@echo "Checking required tools..."
	@command -v $(PYTHON) >/dev/null || (echo "ERROR: Python 3 is required." && exit 1)
	@command -v pnpm >/dev/null || (echo "ERROR: pnpm is required. Install with: corepack enable" && exit 1)
	@command -v docker >/dev/null || echo "WARNING: Docker is not installed. Required for make dev-up."
	@if [ ! -d "$(VENV)" ]; then \
		$(PYTHON) -m venv "$(VENV)"; \
		echo "Created virtual environment at .venv"; \
	fi
	"$(VENV_BIN)/pip" install --upgrade pip
	"$(VENV_BIN)/pip" install -r requirements.txt
	pnpm install
	@echo ""
	@echo "Install complete."
	@echo "Next: make dev-up"

ensure-env:
	@./scripts/ensure-env.sh

dev-up: ensure-env
	@chmod +x scripts/*.sh
	@./scripts/dev-up.sh

dev-down:
	@./scripts/dev-down-host.sh
	$(COMPOSE) down

dev-restart: dev-down dev-up

dev-logs:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) logs -f $(SERVICE); \
	else \
		$(COMPOSE) logs -f postgres api web; \
	fi

db-up: ensure-env
	$(COMPOSE) up -d postgres
	@chmod +x scripts/wait-for-postgres.sh
	@./scripts/wait-for-postgres.sh

db-down:
	$(COMPOSE) stop postgres

db-migrate: ensure-env db-up
	$(COMPOSE) run --rm migrate

db-reset:
	@echo "WARNING: This destroys the local AI-CIO development database."
	@read -r -p "Type 'reset' to continue: " confirm; \
	if [ "$$confirm" != "reset" ]; then echo "Aborted."; exit 1; fi
	$(COMPOSE) down -v
	$(MAKE) db-up
	$(MAKE) db-migrate
	@echo "Database reset complete."

test: ensure-env
	@chmod +x scripts/wait-for-postgres.sh
	@$(COMPOSE) up -d postgres
	@./scripts/wait-for-postgres.sh
	@set -a && source .env && set +a; \
	PYTHONPATH=apps/api "$(VENV_BIN)/pytest" -q || PYTHONPATH=apps/api pytest -q

lint:
	pnpm lint

typecheck:
	pnpm typecheck

build:
	pnpm build

clean:
	rm -rf apps/web/.next
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
