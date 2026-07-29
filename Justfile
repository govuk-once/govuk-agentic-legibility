default:
    @just --list

build:
    uv sync

test:
    uv run pytest -vrrP --testdox --cov agents/src agents/tests

api:
    uv run uvicorn agents.src.workflow_executor.api:create_app --factory --reload --port 8001

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
    uv run pydoclint agents

check: build test lint docs audit scan types