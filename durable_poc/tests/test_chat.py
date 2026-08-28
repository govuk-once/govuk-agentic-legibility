"""Tests for the FastAPI WebSocket chat server and option generation functions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent.chat import app, clean_text_pipes, get_options_from_state


# ---------------------------------------------------------------------------
# Unit Tests for Helper Functions
# ---------------------------------------------------------------------------


def test_clean_text_pipes_removes_standalone_pipes() -> None:
    """clean_text_pipes strips leading and trailing vertical pipe characters from text lines."""
    raw_text = "| Hello World |\n| This is a test |"
    cleaned = clean_text_pipes(raw_text)
    assert cleaned == "Hello World\nThis is a test"


def test_get_options_from_state_boolean() -> None:
    """Boolean schema kind generates Yes/No options."""
    state = {"awaiting": {"schema": {"kind": "boolean"}}}
    options = get_options_from_state(state)
    assert options == ["Yes", "No"]


def test_get_options_from_state_enum() -> None:
    """Enum schema kind uses labels map or raw values."""
    state = {
        "awaiting": {
            "schema": {
                "kind": "enum",
                "values": ["VAL_1", "VAL_2"],
                "labels": {"VAL_1": "Value One"},
            }
        }
    }
    options = get_options_from_state(state)
    assert options == ["Value One", "VAL_2"]


def test_get_options_from_state_select_one() -> None:
    """Select_one schema kind parses label keys from options dicts."""
    state = {
        "awaiting": {
            "options": [
                {"uprn": "100", "single_line": "10 Downing Street"},
                {"uprn": "101", "single_line": "11 Downing Street"},
            ],
            "schema": {
                "kind": "select_one",
                "label_key": "single_line",
                "value_key": "uprn",
            },
        }
    }
    options = get_options_from_state(state)
    assert options == [
        "100 Downing Street" if False else "10 Downing Street",
        "11 Downing Street",
    ]


def test_get_options_from_state_none_when_not_awaiting() -> None:
    """Returns empty list when workflow is not awaiting input."""
    assert get_options_from_state(None) == []
    assert get_options_from_state({"awaiting": None}) == []


# ---------------------------------------------------------------------------
# FastAPI Route & WebSocket Endpoints Test
# ---------------------------------------------------------------------------


def test_get_index_returns_html() -> None:
    """The root endpoint serves the HTML UI template."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>GOV.UK Chat Assistant</title>" in response.text


def test_websocket_connection_disconnects_cleanly() -> None:
    """WebSocket connection connects and disconnects without raising errors."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Verify connection was accepted
        assert websocket is not None
