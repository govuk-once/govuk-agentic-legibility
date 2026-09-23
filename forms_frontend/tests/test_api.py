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
    old_awaiting = mock_temporal._awaiting
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
        # The pre-submission query must still expose the token being answered;
        # only the submit_input response represents the next state.
        mock_temporal.set_awaiting(old_awaiting)

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

    old_awaiting = mock_temporal._awaiting
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
        mock_temporal.set_awaiting(old_awaiting)

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


def test_submit_waits_for_temporal_to_advance_past_old_token(api_client, mock_temporal):
    """A Temporal update can be acknowledged before the workflow loop advances.

    The API must not return the just-submitted question again simply because the
    first post-update query still observes its old awaiting token.
    """
    old_awaiting = {
        "token": "tkn_1",
        "prompt": "When did your holiday year start?",
        "schema": {"kind": "string"},
        "state_id": "holiday_year_start",
        "state_type": "input",
        "timeout_seconds": None,
    }
    next_awaiting = {
        "token": "tkn_2",
        "prompt": "How many days were you entitled to take?",
        "schema": {"kind": "string"},
        "state_id": "holiday_entitlement",
        "state_type": "input",
        "timeout_seconds": None,
    }
    mock_temporal.set_awaiting(old_awaiting)
    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    stale_state = {
        "workflow_id": "sfsm-govuk.forms.2130-test1234",
        "status": "RUNNING",
        "awaiting": old_awaiting,
        "transcript": [],
    }
    advanced_state = {**stale_state, "awaiting": next_awaiting}

    with (
        patch("agent.tools.submit_input", new_callable=AsyncMock, return_value=stale_state),
        patch(
            "agent.tools.get_workflow_state",
            new_callable=AsyncMock,
            side_effect=[stale_state, advanced_state],
        ) as mock_state,
    ):
        resp = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "tkn_1", "value": "01/01/2026"},
        )

    assert resp.status_code == 200
    assert resp.json()["awaiting"]["token"] == "tkn_2"
    assert mock_state.await_count == 2


def test_final_zero_answer_waits_for_completed_state(api_client, mock_temporal):
    """Submitting the valid string value '0' must not redisplay the final input."""
    final_awaiting = {
        "token": "tkn_final",
        "prompt": "How many days were you entitled to take?",
        "schema": {"kind": "string", "allow_skip": True, "default": ""},
        "state_id": "holiday_entitlement",
        "state_type": "input",
        "timeout_seconds": None,
    }
    mock_temporal.set_awaiting(final_awaiting)
    start_resp = api_client.post("/api/sessions", json={"form_id": "2130"})
    session_id = start_resp.json()["session_id"]

    stale_state = {
        "workflow_id": "sfsm-govuk.forms.2130-test1234",
        "status": "RUNNING",
        "awaiting": final_awaiting,
        "transcript": [],
    }
    completed_state = {
        "workflow_id": "sfsm-govuk.forms.2130-test1234",
        "status": "COMPLETED",
        "awaiting": None,
        "transcript": [],
    }

    with (
        patch("agent.tools.submit_input", new_callable=AsyncMock, return_value=stale_state) as mock_submit,
        patch(
            "agent.tools.get_workflow_state",
            new_callable=AsyncMock,
            side_effect=[stale_state, completed_state],
        ),
    ):
        resp = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "tkn_final", "value": "0"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"
    assert resp.json()["awaiting"] is None
    assert mock_submit.call_args.kwargs["value"] == "0"


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
        assert resp.status_code == 409


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


# =====================================================================
# Fixtures
# =====================================================================


def test_list_fixtures(api_client):
    resp = api_client.get("/api/fixtures")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    ids = [f["id"] for f in data]
    assert "form-6-full-details" in ids
    assert "form-6-partial-details" in ids
    assert "form-2130-feedback" in ids


def test_get_fixture(api_client):
    resp = api_client.get("/api/fixtures/form-6-full-details")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "form-6-full-details"
    assert data["form_id"] == "6"
    assert len(data["conversation"]) == 7
    assert data["conversation"][0]["role"] == "user"
    assert "Sarah Thompson" in data["conversation"][0]["content"]


def test_get_fixture_not_found(api_client):
    resp = api_client.get("/api/fixtures/nonexistent")
    assert resp.status_code == 404


def test_fixture_has_form_id(api_client):
    resp = api_client.get("/api/fixtures")
    data = resp.json()
    for fixture in data:
        assert fixture["form_id"] is not None
        assert fixture["message_count"] > 0


def test_start_session_with_fixture(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "What is your full name?",
        "schema": {"kind": "string"},
        "state_id": "uyQrCFqM",
        "state_type": "input",
        "timeout_seconds": None,
    })

    resp = api_client.post(
        "/api/sessions",
        json={
            "form_id": "2130",
            "policy": "confirm",
            "fixture_id": "form-6-full-details",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fixture_id"] == "form-6-full-details"
    assert data["conversation_messages"] == 7
    assert data["policy"] == "confirm"


def test_start_session_without_fixture(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "Q1",
        "schema": {"kind": "string"},
        "state_id": "s1",
        "state_type": "input",
        "timeout_seconds": None,
    })

    resp = api_client.post(
        "/api/sessions",
        json={"form_id": "2130"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fixture_id"] is None
    assert data["conversation_messages"] == 0


def test_start_session_with_nonexistent_fixture(api_client, mock_temporal):
    mock_temporal.set_awaiting({
        "token": "tkn_1",
        "prompt": "Q1",
        "schema": {"kind": "string"},
        "state_id": "s1",
        "state_type": "input",
        "timeout_seconds": None,
    })

    resp = api_client.post(
        "/api/sessions",
        json={"form_id": "2130", "fixture_id": "does-not-exist"},
    )
    assert resp.status_code == 200
    assert resp.json()["conversation_messages"] == 0

# =====================================================================
# Automatic-mode handoff: Temporal stays authoritative when the agent
# encounters a question it cannot answer.
# =====================================================================


def test_auto_progress_stops_at_unknown_question(api_client, mock_temporal):
    from forms_frontend.api import main as api_main

    awaiting = {
        "token": "tkn_holiday_start",
        "prompt": "When did your holiday (leave) year start?",
        "schema": {"kind": "string", "allow_skip": True},
        "state_id": "B9LuEbyQ",
    }
    mock_temporal.set_awaiting(awaiting)
    session_id = api_client.post(
        "/api/sessions", json={"form_id": "6", "policy": "auto"}
    ).json()["session_id"]

    with (
        patch.object(api_main, "propose_answer", new_callable=AsyncMock) as propose,
        patch("agent.tools.submit_input", new_callable=AsyncMock) as submit,
    ):
        propose.return_value = {"has_answer": False, "value": None}
        resp = api_client.get(f"/api/sessions/{session_id}/auto-progress")

    assert resp.status_code == 200
    assert "event: waiting" in resp.text
    assert '"reason": "needs_input"' in resp.text
    submit.assert_not_called()
    state = api_client.get(f"/api/sessions/{session_id}/state").json()
    assert state["awaiting"]["token"] == "tkn_holiday_start"
    assert state["policy"] == "auto"  # No implicit switch to Manual mode.


def test_auto_progress_can_resume_after_manual_answer(api_client, mock_temporal):
    from forms_frontend.api import main as api_main
    from forms_frontend.api.sessions import AutoAnsweredQuestion

    mock_temporal.set_awaiting({
        "token": "tkn_holiday_start",
        "prompt": "When did your holiday (leave) year start?",
        "schema": {"kind": "string", "allow_skip": True},
        "state_id": "B9LuEbyQ",
    })
    session_id = api_client.post(
        "/api/sessions", json={"form_id": "6", "policy": "auto"}
    ).json()["session_id"]
    session = api_main.store.get(session_id)
    assert session is not None
    # Simulate an earlier, successful automatic pass. The 20-step limit must
    # apply to each pass, not to the cumulative session count.
    session.auto_answered.extend(
        AutoAnsweredQuestion(str(i), f"Question {i}", f"Answer {i}")
        for i in range(20)
    )

    new_awaiting = {
        "token": "tkn_next",
        "prompt": "How many days were you entitled to take?",
        "schema": {"kind": "string", "allow_skip": True},
        "state_id": "VRYgtG3z",
    }
    with patch("agent.tools.submit_input", new_callable=AsyncMock) as submit:
        submit.return_value = {"status": "RUNNING", "awaiting": new_awaiting}
        resp = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "tkn_holiday_start", "value": "01/01/2026"},
        )
    assert resp.status_code == 200
    assert resp.json()["awaiting"]["token"] == "tkn_next"
    assert session.policy.value == "auto"

    # Mock Temporal's authoritative state after it accepted the manual answer.
    mock_temporal.set_awaiting(new_awaiting)
    with patch.object(api_main, "propose_answer", new_callable=AsyncMock) as propose:
        propose.return_value = {"has_answer": False, "value": None}
        resumed = api_client.get(f"/api/sessions/{session_id}/auto-progress")
    assert resumed.status_code == 200
    assert '"reason": "needs_input"' in resumed.text
    assert '"steps_taken": 20' in resumed.text
    assert '"reason": "max_steps"' not in resumed.text
