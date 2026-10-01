default:
    @just --list

build:
    uv sync

test:
    uv run pytest -vrrP --testdox --cov agents/src agents/tests

test-poc:
    uv run pytest -vrrP --testdox --cov durable_poc/src durable_poc/tests

api:
    uv run uvicorn agents.src.workflow_executor.api:create_app --factory --reload --port 8001

durable-api:
    cd durable_poc && uv run uvicorn agent.api.app:create_app --factory --reload --port 8010

durable-frontend-install:
    pnpm --prefix durable-frontend install

durable-frontend:
    pnpm --prefix durable-frontend run dev

durable-frontend-check:
    pnpm --prefix durable-frontend run check

durable-frontend-build:
    pnpm --prefix durable-frontend run build

format:
    uv run ruff format

lint:
    uv run ruff check --fix

audit:
    uv run pip-audit

scan:
    uv run bandit -r agents/src

types:
    uv run mypy agents/src agents/tests

docs:
    uvx --from pydoclint==0.9.1 pydoclint agents

check: build test test-poc lint docs audit scan types

frontend-install:
    npm --prefix frontend install

frontend:
    npm --prefix frontend run dev -- --host 127.0.0.1

frontend-check:
    npm --prefix frontend run check

frontend-build:
    npm --prefix frontend run build

check-all: check frontend-check
