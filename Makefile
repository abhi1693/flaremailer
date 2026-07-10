SHELL := /bin/bash
ROOT := $(CURDIR)
BACKEND_ENV_FILE ?= $(ROOT)/apps/backend/.env
FRONTEND_ENV_FILE ?= $(ROOT)/apps/frontend/.env
LOAD_BACKEND_ENV = set -euo pipefail; set -a; source "$(BACKEND_ENV_FILE)"; set +a
LOAD_FRONTEND_ENV = set -euo pipefail; set -a; source "$(FRONTEND_ENV_FILE)"; set +a
FRONTEND_ENV = env \
	-u DATABASE_URL -u PGPASSWORD -u PGHOST -u PGPORT -u PGDATABASE -u PGUSER \
	-u SESSION_SECRET -u CREDENTIAL_ENCRYPTION_KEY

.DEFAULT_GOAL := help
.PHONY: help env backend-env frontend-env install backend-install frontend-install \
	db-check db-shell migrate \
	backend worker frontend dev backend-test backend-check frontend-check frontend-build \
	orval check

help:
	@echo "Flaremailer developer commands"
	@echo "  make env          Create private backend and frontend .env files"
	@echo "  make install      Install Python and Node dependencies"
	@echo "  make db-check     Check the configured PostgreSQL server"
	@echo "  make migrate      Apply pending Alembic migrations"
	@echo "  make dev          Run backend, worker, and frontend together"
	@echo "  make backend      Run only the FastAPI backend with reload"
	@echo "  make worker       Run only the delivery worker"
	@echo "  make frontend     Run only the Next.js frontend"
	@echo "  make orval        Regenerate the client from a running API"
	@echo "  make check        Run all backend and frontend checks"

env: backend-env frontend-env

backend-env:
	@test -f "$(BACKEND_ENV_FILE)" || { install -m 600 apps/backend/.env.example "$(BACKEND_ENV_FILE)"; echo "Created $(BACKEND_ENV_FILE); update its secrets and PostgreSQL URL."; }
	@chmod 600 "$(BACKEND_ENV_FILE)"

frontend-env:
	@test -f "$(FRONTEND_ENV_FILE)" || { install -m 600 apps/frontend/.env.example "$(FRONTEND_ENV_FILE)"; echo "Created $(FRONTEND_ENV_FILE); update its API origin when needed."; }
	@chmod 600 "$(FRONTEND_ENV_FILE)"

install: backend-install frontend-install

backend-install:
	cd apps/backend && uv sync --all-groups

frontend-install:
	cd apps/frontend && corepack pnpm install --frozen-lockfile

db-check: backend-env
	@$(LOAD_BACKEND_ENV); psql -X -v ON_ERROR_STOP=1 -tAc 'SELECT 1' >/dev/null && echo "PostgreSQL connection and credentials are valid."

db-shell: backend-env
	@$(LOAD_BACKEND_ENV); psql

migrate: backend-env
	@$(LOAD_BACKEND_ENV); cd apps/backend && uv run alembic upgrade head

backend: backend-env
	@$(LOAD_BACKEND_ENV); cd apps/backend && uv run uvicorn app.main:app --reload --host "$${BACKEND_HOST:-127.0.0.1}" --port "$${BACKEND_PORT:-8000}"

worker: backend-env
	@$(LOAD_BACKEND_ENV); cd apps/backend && uv run python -m app.worker

frontend: frontend-env
	@$(LOAD_FRONTEND_ENV); cd apps/frontend && $(FRONTEND_ENV) corepack pnpm dev --hostname "$${FRONTEND_HOST:-127.0.0.1}" --port "$${FRONTEND_PORT:-3000}"

dev: env
	@($(LOAD_BACKEND_ENV); cd apps/backend && uv run uvicorn app.main:app --reload --host "$${BACKEND_HOST:-127.0.0.1}" --port "$${BACKEND_PORT:-8000}") & backend_pid=$$!; \
	($(LOAD_BACKEND_ENV); cd apps/backend && uv run python -m app.worker) & worker_pid=$$!; \
	($(LOAD_FRONTEND_ENV); cd apps/frontend && $(FRONTEND_ENV) corepack pnpm dev --hostname "$${FRONTEND_HOST:-127.0.0.1}" --port "$${FRONTEND_PORT:-3000}") & frontend_pid=$$!; \
	trap 'kill $$backend_pid $$worker_pid $$frontend_pid 2>/dev/null || true' INT TERM EXIT; \
	wait -n $$backend_pid $$worker_pid $$frontend_pid; status=$$?; \
	kill $$backend_pid $$worker_pid $$frontend_pid 2>/dev/null || true; \
	wait 2>/dev/null || true; \
	exit $$status

backend-test:
	cd apps/backend && uv run --group dev pytest

backend-check:
	cd apps/backend && uv run --group dev ruff check .
	cd apps/backend && uv run --group dev ruff format --check .
	cd apps/backend && uv run --group dev mypy app

frontend-check:
	cd apps/frontend && corepack pnpm lint
	cd apps/frontend && corepack pnpm typecheck
	cd apps/frontend && corepack pnpm test

frontend-build: frontend-env
	@$(LOAD_FRONTEND_ENV); cd apps/frontend && $(FRONTEND_ENV) corepack pnpm build

orval: frontend-env
	@$(LOAD_FRONTEND_ENV); api_origin="$${API_INTERNAL_URL:-http://127.0.0.1:8000}"; cd apps/frontend && \
		$(FRONTEND_ENV) ORVAL_INPUT="$${ORVAL_INPUT:-$${api_origin%/}/openapi.json}" \
		corepack pnpm generate:api

check: backend-test backend-check frontend-check frontend-build
