"""Tests for the FastAPI WebSockets interface, options extractor, and event trace stream."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient

from agent.chat import app, get_options_from_state


# ---------------------------------------------------------------------------
# Unit Tests for Helper Functions
# ---------------------------------------------------------------------------


def test_get_options_from_state_boolean() -> None:
    """Boolean schema kind generates Yes/No options with kind indicator."""
    state = {"awaiting": {"schema": {"kind": "boolean"}}}
    result = get_options_from_state(state)
    assert result == {"kind": "boolean", "options": ["Yes", "No"]}


def test_get_options_from_state_select_one_dict() -> None:
    """Select_one schema kind parses label keys from options dicts."""
    state = {
        "awaiting": {
            "options": [
                {"uprn": "1000", "single_line": "10 Downing Street"},
                {"uprn": "1001", "single_line": "11 Downing Street"},
            ],
            "schema": {"kind": "select_one", "label_key": "single_line"},
        }
    }
    result = get_options_from_state(state)
    assert result == {
        "kind": "select_one",
        "options": ["10 Downing Street", "11 Downing Street"],
    }


def test_get_options_from_state_select_many_dict() -> None:
    """Select_many schema kind returns options list and specifies kind='select_many'."""
    state = {
        "awaiting": {
            "schema": {
                "kind": "select_many",
                "options": [
                    {"value": "employed", "label": "Employed (including agency work)"},
                    {"value": "self_employed", "label": "Self-employed"},
                ],
            }
        }
    }
    result = get_options_from_state(state)
    assert result == {
        "kind": "select_many",
        "options": ["Employed (including agency work)", "Self-employed"],
    }


# ---------------------------------------------------------------------------
# FastAPI Route & WebSocket Endpoints Test
# ---------------------------------------------------------------------------


def test_get_index_renders_html_interface() -> None:
    """The root endpoint serves the HTML UI template."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "GOV.UK Chat Assistant" in response.text
    assert "Execution Events" in response.text
    assert "workflow-picker" in response.text


@pytest.mark.asyncio
async def test_websocket_connection_and_trace_stream() -> None:
    """WebSocket accepts connections and broadcasts initial active workflow choices."""
    mock_agent = MagicMock()

    mock_polling_client = AsyncMock()

    # Patch agent_instance, polling client, and list_active_workflows to prevent gRPC hangs
    with (
        patch("agent.chat.create_agent", return_value=mock_agent),
        patch("agent.chat._get_polling_client", AsyncMock(return_value=mock_polling_client)),
        patch("agent.chat.tool_functions.list_active_workflows",AsyncMock(return_value=[]))
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "active_workflows"
            assert isinstance(data["workflows"], list)
