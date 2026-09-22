"""Tests for the forms_frontend API.

These tests mock Temporal and Bedrock — no live services required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_repo = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo / "durable_poc"))


# =====================================================================
# Listing forms
# =====================================================================


def test_list_forms(api_client):
    resp = api_client.get("/api/forms")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["id"] == 2130


# =====================================================================
# Starting a session
# =====================================================================


def test_start_session(api_client, mock_temporal):
    first_awaiting = {
        "token": "tkn_1",
        "prompt": "How are you using this service?",
        "schema": {
            "kind": "select_one",
            "options": [
                {"value": "public", "label": "As a member of the public"},
            ],
        },
        "state_id": "Z9qiMdb6",
        "state_type": "input",
        "timeout_seconds": None,
    }
    mock_temporal.set_awaiting(first_awaiting)

    resp = api_client.post(
        "/api/sessions",
        json={"form_id": "2130", "policy": "manual"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"]
    assert data["form_name"] == "Give feedback on Search for local land charges"
    assert data["policy"] == "manual"


def test_start_session_with_confirm_policy(api_client, mock_temporal):
    mock_temporal.set_awaiting({"token": "tkn_1", "prompt": "Q1", "schema": {"kind": "string"}})
    resp = api_client.post(
        "/api/sessions",
        json={"form_id": "2130", "policy": "confirm"},
    )
    assert resp.status_code == 200
    assert resp.json()["policy"] == "confirm"


# =====================================================================
# Getting session state
# =====================================================================


def test_get_session_state(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "How are you using this service?",
        "schema": {"kind": "select_one", "options": []},
        "state_id": "Z9qiMdb6",
        "state_type": "input",
        "timeout_seconds": None,
    })

    start_resp = api_client.post(
        "/api/sessions", json={"form_id": "2130"}
    )
    session_id = start_resp.json()["session_id"]

    resp = api_client.get(f"/api/sessions/{session_id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["awaiting"]["token"] == "tkn_1"
    assert data["policy"] == "manual"


def test_get_session_state_not_found(api_client):
    resp = api_client.get("/api/sessions/nonexistent/state")
    assert resp.status_code == 404


# =====================================================================
# Submitting answers
# =====================================================================


def test_submit_string_answer(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "How could we improve?",
        "schema": {"kind": "string"},
        "state_id": "oygaerZY",
        "state_type": "input",
        "timeout_seconds": None,
    })

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    # After submit, advance to next question
    mock_temporal.set_awaiting({
        "token": "tkn_2",
        "prompt": "Did you receive any assistance?",
        "schema": {"kind": "boolean"},
        "state_id": "mq4KgkUb",
        "state_type": "input",
        "timeout_seconds": None,
    })

    with patch("agent.tools.submit_input", new_callable=AsyncMock) as mock_submit:
        mock_submit.return_value = {
            "workflow_id": "sfsm-govuk.forms.2130-test1234",
            "status": "RUNNING",
            "awaiting": mock_temporal._awaiting,
            "transcript": [],
        }

        resp = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "tkn_1", "value": "The map was confusing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["awaiting"]["token"] == "tkn_2"

        mock_submit.assert_called_once()
        call_kwargs = mock_submit.call_args.kwargs
        assert call_kwargs["token"] == "tkn_1"
        assert call_kwargs["value"] == "The map was confusing"


def test_submit_boolean_answer(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "Did you receive any assistance?",
        "schema": {"kind": "boolean"},
        "state_id": "mq4KgkUb",
        "state_type": "input",
        "timeout_seconds": None,
    })

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    mock_temporal.set_awaiting({
        "token": "tkn_3",
        "prompt": "Email?",
        "schema": {"kind": "string"},
        "state_id": "31pMZdRv",
        "state_type": "input",
        "timeout_seconds": None,
    })

    with patch("agent.tools.submit_input", new_callable=AsyncMock) as mock_submit:
        mock_submit.return_value = {
            "workflow_id": "sfsm-govuk.forms.2130-test1234",
            "status": "RUNNING",
            "awaiting": mock_temporal._awaiting,
            "transcript": [],
        }

        resp = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "tkn_1", "value": False},
        )
        assert resp.status_code == 200
        call_kwargs = mock_submit.call_args.kwargs
        assert call_kwargs["value"] is False


def test_submit_select_one_answer(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "How are you using this service?",
        "schema": {
            "kind": "select_one",
            "options": [
                {"value": "public", "label": "As a member of the public"},
                {"value": "professional", "label": "As a professional"},
            ],
        },
        "state_id": "Z9qiMdb6",
        "state_type": "input",
        "timeout_seconds": None,
    })

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    with patch("agent.tools.submit_input", new_callable=AsyncMock) as mock_submit:
        mock_submit.return_value = {
            "workflow_id": "sfsm-govuk.forms.2130-test1234",
            "status": "RUNNING",
            "awaiting": None,
            "transcript": [],
        }
        resp = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "tkn_1", "value": "public"},
        )
        assert resp.status_code == 200
        assert mock_submit.call_args.kwargs["value"] == "public"


# =====================================================================
# Optional fields
# =====================================================================


def test_submit_optional_empty(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "Email (optional)?",
        "schema": {"kind": "string", "allow_skip": True, "default": ""},
        "state_id": "31pMZdRv",
        "state_type": "input",
        "timeout_seconds": None,
    })

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    mock_temporal.set_status("COMPLETED")
    mock_temporal.set_awaiting(None)

    with patch("agent.tools.submit_input", new_callable=AsyncMock) as mock_submit:
        mock_submit.return_value = {
            "workflow_id": "sfsm-govuk.forms.2130-test1234",
            "status": "COMPLETED",
            "awaiting": None,
            "transcript": [],
        }
        resp = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "tkn_1", "value": ""},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"


# =====================================================================
# Stale token handling
# =====================================================================


def test_submit_stale_token(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_2",
        "prompt": "Q2",
        "schema": {"kind": "string"},
        "state_id": "s2",
        "state_type": "input",
        "timeout_seconds": None,
    })

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    with patch("agent.tools.submit_input", new_callable=AsyncMock) as mock_submit:
        mock_submit.side_effect = Exception("Stale token: expected tkn_2, got tkn_1")

        resp = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "tkn_1", "value": "stale answer"},
        )
        assert resp.status_code == 400


# =====================================================================
# Completed workflow
# =====================================================================


def test_completed_workflow_state(api_client, mock_temporal):
    mock_temporal.set_awaiting(None)
    mock_temporal.set_status("COMPLETED")

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    resp = api_client.get(f"/api/sessions/{session_id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert data["awaiting"] is None


# =====================================================================
# Policy change
# =====================================================================


def test_set_policy(api_client, mock_temporal):
    mock_temporal.set_awaiting({"token": "tkn_1", "prompt": "Q1", "schema": {"kind": "string"}, "state_id": "s1", "state_type": "input", "timeout_seconds": None})

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    resp = api_client.put(
        f"/api/sessions/{session_id}/policy",
        json={"policy": "confirm"},
    )
    assert resp.status_code == 200
    assert resp.json()["policy"] == "confirm"


def test_set_invalid_policy(api_client, mock_temporal):
    mock_temporal.set_awaiting({"token": "tkn_1", "prompt": "Q1", "schema": {"kind": "string"}, "state_id": "s1", "state_type": "input", "timeout_seconds": None})

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    resp = api_client.put(
        f"/api/sessions/{session_id}/policy",
        json={"policy": "invalid_policy"},
    )
    assert resp.status_code == 400


# =====================================================================
# Presentation metadata
# =====================================================================


def test_presentation_metadata_returned(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "How are you using this service?",
        "schema": {
            "kind": "select_one",
            "options": [],
            "presentation": {
                "source": "govuk_forms",
                "step_id": "Z9qiMdb6",
                "position": 1,
                "question_text": "How are you using this service?",
                "answer_type": "selection",
                "answer_settings": {"only_one_option": "true"},
                "is_optional": False,
                "required": True,
            },
        },
        "state_id": "Z9qiMdb6",
        "state_type": "input",
        "timeout_seconds": None,
    })

    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    resp = api_client.get(f"/api/sessions/{session_id}/state")
    data = resp.json()
    assert data["presentation"] is not None
    assert data["presentation"]["answer_type"] == "selection"
