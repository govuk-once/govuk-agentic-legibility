"""Tests for the FastAPI WebSockets interface, options extractor, and event trace stream."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient

from agent.chat import app, clean_text_pipes, get_options_from_state


# ---------------------------------------------------------------------------
# Unit Tests for Helper Functions
# ---------------------------------------------------------------------------


def test_clean_text_pipes_removes_standalone_pipes() -> None:
    """clean_text_pipes strips leading and trailing vertical pipe characters from text lines."""
    raw_text = "| Welcome to GOV.UK |\n| Please confirm your address |"
    cleaned = clean_text_pipes(raw_text)
    assert cleaned == "Welcome to GOV.UK\nPlease confirm your address"


def test_get_options_from_state_boolean() -> None:
    """Boolean schema kind generates Yes/No options."""
    state = {"awaiting": {"schema": {"kind": "boolean"}}}
    assert get_options_from_state(state) == ["Yes", "No"]


def test_get_options_from_state_enum() -> None:
    """Enum schema kind uses labels map or raw values."""
    state = {
        "awaiting": {
            "schema": {
                "kind": "enum",
                "values": ["OPT_A", "OPT_B"],
                "labels": {"OPT_A": "Option A"},
            }
        }
    }
    assert get_options_from_state(state) == ["Option A", "OPT_B"]


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
    assert get_options_from_state(state) == ["10 Downing Street", "11 Downing Street"]


# ---------------------------------------------------------------------------
# FastAPI Route & WebSocket Endpoints Test
# ---------------------------------------------------------------------------


def test_get_index_renders_html_interface() -> None:
    """The root endpoint serves the HTML UI template."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "GOV.UK Chat Assistant" in response.text
    assert "Execution Event Trace" in response.text
    assert "workflow-picker" in response.text


@pytest.mark.asyncio
async def test_websocket_connection_and_trace_stream() -> None:
    """WebSocket accepts connections and broadcasts initial active workflow choices."""
    mock_agent = MagicMock()
    mock_agent._get_temporal_client = AsyncMock()

    # Patch agent_instance and list_active_workflows to prevent gRPC hangs
    with (
        patch("agent.chat.agent_instance", mock_agent),
        patch("agent.tools.list_active_workflows", AsyncMock(return_value=[])),
    ):
        # TestClient inside synchronous wrapper
        client = TestClient(app)
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "active_workflows"
            assert isinstance(data["workflows"], list)
