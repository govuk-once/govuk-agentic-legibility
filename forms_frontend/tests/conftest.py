"""Test fixtures for forms_frontend.

All tests use mocks for Temporal and Bedrock — no live services required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure durable_poc imports work
_repo = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo / "durable_poc"))

FIXTURES_DIR = _repo / "compiled_forms"


def _compiled_fixture(form_id: str) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{form_id}.json"
    if path.is_file():
        return json.loads(path.read_text())
    # The ZIP intentionally omits gitignored generated compiled_forms. Compile
    # the checked-in original export so the test suite runs from a clean clone.
    from forms_adapter import compile_form
    export = _repo / "durable_poc" / "forms_adapter" / "tests" / "fixtures" / f"{form_id}.json"
    return compile_form(json.loads(export.read_text()))


@pytest.fixture
def form_2130_definition() -> dict[str, Any]:
    return _compiled_fixture("2130")


@pytest.fixture
def form_6_definition() -> dict[str, Any]:
    return _compiled_fixture("6")


def _make_awaiting(
    *,
    token: str = "tkn_1",
    prompt: str = "Test question?",
    schema: dict | None = None,
    state_id: str = "test_state",
) -> dict[str, Any]:
    """Helper to create an awaiting-input dict."""
    if schema is None:
        schema = {"kind": "string"}
    return {
        "token": token,
        "prompt": prompt,
        "schema": schema,
        "options": schema.get("options"),
        "timeout_seconds": None,
        "state_id": state_id,
        "state_type": "input",
    }


@pytest.fixture
def mock_awaiting():
    return _make_awaiting


class MockTemporalClient:
    """Simulates the Temporal client for testing."""

    def __init__(self) -> None:
        self.started_workflows: list[dict] = []
        self._state: dict[str, Any] = {}
        self._awaiting: dict[str, Any] | None = None
        self._transcript: list[dict] = []
        self._status = "RUNNING"

    def set_awaiting(self, awaiting: dict[str, Any] | None) -> None:
        self._awaiting = awaiting

    def set_status(self, status: str) -> None:
        self._status = status

    async def start_workflow(self, *args: Any, **kwargs: Any) -> MagicMock:
        handle = MagicMock()
        handle.id = kwargs.get("id", "sfsm-test-workflow")
        self.started_workflows.append(kwargs)
        return handle

    def get_workflow_handle(self, workflow_id: str) -> MagicMock:
        handle = MagicMock()
        handle.id = workflow_id

        async def mock_describe():
            desc = MagicMock()
            desc.status = MagicMock()
            desc.status.name = self._status
            return desc

        async def mock_query(name: str):
            if name == "awaiting":
                return self._awaiting
            if name == "transcript":
                return self._transcript
            return None

        async def mock_execute_update(name: str, arg: Any):
            pass

        handle.describe = mock_describe
        handle.query = mock_query
        handle.execute_update = mock_execute_update
        return handle


@pytest.fixture
def mock_temporal():
    return MockTemporalClient()


@pytest.fixture
def api_client(mock_temporal, form_2130_definition):
    """FastAPI TestClient with mocked Temporal and workflow server."""
    from forms_frontend.api import main as api_main

    async def fake_temporal():
        return mock_temporal

    async def fake_http():
        return MagicMock()

    with (
        patch.object(api_main, "get_temporal_client", fake_temporal),
        patch.object(api_main, "get_http_client", fake_http),
        patch(
            "agent.tools.list_available_workflows",
            new_callable=AsyncMock,
            return_value=[
                {"id": 2130, "name": "Give feedback on Search for local land charges", "slug": "give-feedback"},
                {"id": 6, "name": "Amend my claim for holiday pay accrued", "slug": "amend-holiday-pay"},
            ],
        ),
        patch(
            "agent.tools.get_workflow_definition",
            new_callable=AsyncMock,
            return_value=form_2130_definition,
        ),
        patch(
            "agent.tools.start_workflow",
            new_callable=AsyncMock,
            return_value="sfsm-govuk.forms.2130-test1234",
        ),
    ):
        yield TestClient(api_main.app)
