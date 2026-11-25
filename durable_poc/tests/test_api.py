"""Tests for the generalized durable_poc API: routes, watch_run, and chat WS."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider

from agent.api import deps
from agent.api.app import create_app
from agent.api.events import clean_text_pipes, get_options_from_state, watch_run

# ---------------------------------------------------------------------------
# Unit tests for the ported helper functions
# ---------------------------------------------------------------------------


def test_clean_text_pipes_removes_standalone_pipes() -> None:
    """clean_text_pipes strips leading and trailing vertical pipe characters."""
    raw_text = "| Welcome to GOV.UK |\n| Please confirm your address |"
    assert clean_text_pipes(raw_text) == "Welcome to GOV.UK\nPlease confirm your address"


def test_get_options_from_state_boolean() -> None:
    """Boolean schema kind generates Yes/No options."""
    state = {"awaiting": {"schema": {"kind": "boolean"}}}
    assert get_options_from_state(state) == {"kind": "boolean", "options": ["Yes", "No"]}


def test_get_options_from_state_select_one_dict() -> None:
    """select_one schema kind parses label keys from options dicts."""
    state = {
        "awaiting": {
            "options": [
                {"uprn": "1000", "single_line": "10 Downing Street"},
                {"uprn": "1001", "single_line": "11 Downing Street"},
            ],
            "schema": {"kind": "select_one", "label_key": "single_line"},
        }
    }
    assert get_options_from_state(state) == {
        "kind": "select_one",
        "options": ["10 Downing Street", "11 Downing Street"],
    }


# ---------------------------------------------------------------------------
# watch_run
# ---------------------------------------------------------------------------


class _FakeTemporalHandle:
    pass


@pytest.mark.asyncio
async def test_watch_run_yields_message_then_options_then_completes() -> None:
    """watch_run diffs transcript/awaiting across polls and stops at a terminal status."""
    states: list[dict[str, Any]] = [
        {
            "workflow_id": "sfsm-test-1",
            "status": "RUNNING",
            "awaiting": {"token": "t1", "prompt": "What is your name?", "schema": {"kind": "text"}},
            "transcript": [{"message": "Welcome"}],
        },
        {
            "workflow_id": "sfsm-test-1",
            "status": "COMPLETED",
            "awaiting": None,
            "transcript": [{"message": "Welcome"}, {"message": "Thanks, goodbye"}],
        },
    ]

    async def fake_get_workflow_state(*, workflow_id: str, temporal_client: Any) -> dict[str, Any]:
        return states.pop(0)

    with patch("agent.api.events.tool_functions.get_workflow_state", fake_get_workflow_state):
        events = [
            event
            async for event in watch_run("sfsm-test-1", temporal_client=object(), poll_interval=0)
        ]

    event_types = [e.type for e in events]
    assert event_types == [
        "message",
        "trace",
        "message",
        "trace",
        "options",
        "message",
        "trace",
        "completed",
    ]
    assert events[0].text == "Welcome"
    assert events[-1].status == "COMPLETED"


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client() -> TestClient:
    with patch("agent.api.app.create_agent_provider", return_value=TracerProvider()):
        app = create_app()
    # Routes depend on live Temporal/httpx clients; tests instead patch the
    # `tool_functions` calls those routes make, so the client objects
    # themselves are never used against a real server.
    app.dependency_overrides[deps.get_polling_client] = lambda: object()
    app.dependency_overrides[deps.get_http_client] = lambda: object()
    return TestClient(app)


def test_healthcheck(api_client: TestClient) -> None:
    """The healthcheck route reports ok."""
    response = api_client.get("/healthcheck")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_workflows_proxies_tool_functions(api_client: TestClient) -> None:
    """GET /api/v1/workflows returns whatever the workflow server has registered."""
    with patch(
        "agent.api.routes.workflows.tool_functions.list_available_workflows",
        AsyncMock(return_value=[{"id": "dvla-coa", "name": "Change of address"}]),
    ):
        response = api_client.get("/api/v1/workflows")
    assert response.status_code == 200
    assert response.json() == [{"id": "dvla-coa", "name": "Change of address"}]


def test_get_run_returns_404_when_missing(api_client: TestClient) -> None:
    """GET /api/v1/runs/{id} surfaces an unknown run as a 404, not a 500."""
    with patch(
        "agent.api.routes.runs.tool_functions.get_workflow_state",
        AsyncMock(side_effect=RuntimeError("not found")),
    ):
        response = api_client.get("/api/v1/runs/does-not-exist")
    assert response.status_code == 404


def test_start_run_and_submit_input(api_client: TestClient) -> None:
    """POST /runs starts a workflow; POST /runs/{id}/input submits a field value."""
    with patch(
        "agent.api.routes.runs.tool_functions.start_workflow",
        AsyncMock(return_value="sfsm-dvla-coa-abcd1234"),
    ):
        start_response = api_client.post("/api/v1/runs", json={"workflow_id": "dvla-coa"})
    assert start_response.status_code == 201
    assert start_response.json() == {"workflow_id": "sfsm-dvla-coa-abcd1234"}

    new_state = {
        "workflow_id": "sfsm-dvla-coa-abcd1234",
        "status": "RUNNING",
        "awaiting": None,
        "transcript": [],
    }
    with patch(
        "agent.api.routes.runs.tool_functions.submit_input",
        AsyncMock(return_value=new_state),
    ):
        submit_response = api_client.post(
            "/api/v1/runs/sfsm-dvla-coa-abcd1234/input",
            json={"token": "t1", "value": "Yes"},
        )
    assert submit_response.status_code == 200
    assert submit_response.json() == new_state


# ---------------------------------------------------------------------------
# Chat WebSocket
# ---------------------------------------------------------------------------


def test_chat_ws_broadcasts_active_workflows_on_connect(api_client: TestClient) -> None:
    """Connecting to /chat immediately broadcasts the active-workflow picker list."""
    with (
        patch("agent.api.routes.chat_ws.deps.new_workflow_agent", return_value=AsyncMock()),
        patch("agent.api.routes.chat_ws.deps.get_polling_client", AsyncMock(return_value=AsyncMock())),
        patch(
            "agent.api.routes.chat_ws.tool_functions.list_active_workflows",
            AsyncMock(return_value=[]),
        ),
    ):
        with api_client.websocket_connect("/chat") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "active_workflows"
            assert data["workflows"] == []
