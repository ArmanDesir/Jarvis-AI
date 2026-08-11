.PHONY: install dev-api dev-worker dev-web lint format format-check typecheck test test-unit test-integration test-architecture build migrate migration-check secret-check ci clean

install:
	uv sync --all-packages --all-groups --locked
	npm ci

dev-api:
	uv run uvicorn rightjob_api.main:app --app-dir apps/api/src --reload

dev-worker:
	uv run python -m rightjob_worker.main

dev-web:
	npm run dev:web

lint:
	uv run ruff check .
	npm run lint:web

format:
	uv run ruff format .
	npm run format:web

format-check:
	uv run ruff format --check .
	npm run format:check:web

typecheck:
	uv run mypy
	npm run typecheck:web

test-unit:
	uv run pytest -m "not integration"
	npm run test:web

test-integration:
	uv run pytest -m integration

test-architecture:
	uv run python scripts/check_architecture.py
	uv run python scripts/check_phase1_scope.py

test: test-unit test-integration test-architecture

build:
	uv build --all-packages
	npm run build:web

migrate:
	uv run alembic upgrade head

migration-check:
	uv run python scripts/check_migrations.py

secret-check:
	uv run python scripts/check_secrets.py

ci: format-check lint typecheck test build migration-check secret-check

clean:
	uv run python scripts/clean.py
