"""Form 6 regression: two agent/user handoffs and one final submission.

Only the LLM and Temporal transport are mocked. The eleven input states,
optional defaults, presentation and transitions come from the real compiler.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forms_frontend.api import main as api
from forms_frontend.api.sessions import SessionStore


class LinearTemporal:
    """Models update acknowledgement, then old input, then no input, then next."""

    def __init__(self, definition):
        states = definition["processes"]["main"]["states"]
        current = definition["processes"]["main"]["start"]
        self.questions = []
        while states[current]["type"] == "input":
            self.questions.append((current, states[current]))
            current = states[current]["next"]
        assert current == "end_form" and len(self.questions) == 11
        self.position = 0
        self.pending = False
        self.old_queries = 0
        self.gap_queries = 0
        self.submissions = []
        self.reject_next = False

    def awaiting(self, position=None):
        if position is None:
            position = self.position
        if position >= len(self.questions):
            return None
        state_id, state = self.questions[position]
        return {
            "token": f"token-{position + 1}", "state_id": state_id,
            "prompt": state["prompt"], "schema": state["schema"],
            "state_type": "InputState",
        }

    def current(self):
        return {
            "status": "COMPLETED" if self.position == 11 else "RUNNING",
            "awaiting": self.awaiting(), "transcript": [],
        }

    async def state(self, **_kwargs):
        if self.pending:
            if self.old_queries > 0:
                self.old_queries -= 1
                return self.current()
            if self.gap_queries > 0:
                self.gap_queries -= 1
                return {"status": "RUNNING", "awaiting": None, "transcript": []}
            self.position += 1
            self.pending = False
        return self.current()

    async def submit(self, *, token, value, **_kwargs):
        assert not self.pending, "A second update was issued before the first advanced"
        assert self.awaiting()["token"] == token
        if self.reject_next:
            self.reject_next = False
            raise ValueError("Invalid selection")
        # Form 6 presents all four optional numbers/dates as SFSM strings.
        assert isinstance(value, str)
        self.submissions.append((self.questions[self.position][0], value))
        self.pending = True
        self.old_queries = 1
        self.gap_queries = 1
        # The Temporal update has succeeded, but queries still see the old token.
        return self.current()

    def get_workflow_handle(self, *_args):
        return self

    async def result(self):
        return {"status": "complete", "outcome": "completed"}


@pytest.fixture
def journey(monkeypatch, form_6_definition):
    fake = LinearTemporal(form_6_definition)
    fixture_path = Path(__file__).parent.parent / "fixtures" / "form_6_partial_details.json"
    conversation_fixture = json.loads(fixture_path.read_text())
    assert conversation_fixture["form_id"] == "6"

    async def get_definition(**_kwargs):
        return form_6_definition

    async def start_workflow(**_kwargs):
        return "test-form-six"

    async def get_temporal():
        return fake

    async def proposal(*, awaiting, conversation_history):
        assert conversation_history == conversation_fixture["conversation"]
        position = next(i for i, (name, _) in enumerate(fake.questions)
                        if name == awaiting["state_id"])
        if position in (7, 10):
            return {"has_answer": False, "value": None, "explanation": "Needs user input"}
        return {"has_answer": True, "value": f"synthetic-{position}", "explanation": "Fixture"}

    monkeypatch.setattr(api, "store", SessionStore())
    monkeypatch.setattr(api, "get_temporal_client", get_temporal)
    monkeypatch.setattr(api, "get_http_client", get_temporal)
    monkeypatch.setattr(api.tool_functions, "get_workflow_definition", get_definition)
    monkeypatch.setattr(api.tool_functions, "start_workflow", start_workflow)
    monkeypatch.setattr(api.tool_functions, "get_workflow_state", fake.state)
    monkeypatch.setattr(api.tool_functions, "submit_input", fake.submit)
    monkeypatch.setattr(api, "propose_answer", proposal)

    with TestClient(api.app) as client:
        started = client.post("/api/sessions", json={
            "form_id": "6", "policy": "auto", "fixture_id": conversation_fixture["id"],
        })
        assert started.status_code == 200
        yield client, started.json()["session_id"], fake


def _events(response):
    assert response.status_code == 200, response.text
    return [json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines() if line.startswith("data: ")]


def _run_to_final(journey):
    client, sid, fake = journey
    first = _events(client.get(f"/api/sessions/{sid}/auto-progress"))
    assert [e["type"] for e in first].count("step") == 7
    assert first[-1]["reason"] == "needs_input"
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["awaiting"]["state_id"] == "B9LuEbyQ"
    assert len(state["auto_answered"]) == state["answered_count"] == 7

    token = state["awaiting"]["token"]
    manual = client.post(f"/api/sessions/{sid}/submit", json={
        "token": token, "value": "01/01/2026",
    })
    assert manual.status_code == 200, manual.text
    assert manual.json()["awaiting"]["state_id"] == "VRYgtG3z"
    assert fake.submissions.count(("B9LuEbyQ", "01/01/2026")) == 1
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["answered_count"] == 8 and len(state["auto_answered"]) == 7

    second = _events(client.get(f"/api/sessions/{sid}/auto-progress"))
    assert [e["type"] for e in second].count("step") == 2
    assert [e["steps_taken"] for e in second if e["type"] == "step"] == [8, 9]
    assert [e["answered_count"] for e in second if e["type"] == "step"] == [9, 10]
    assert second[-1]["reason"] == "needs_input"
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["awaiting"]["state_id"] == "hY9HnrAz"
    assert len(state["auto_answered"]) == 9
    assert state["answered_count"] == 10
    assert state["policy"] == "auto"
    return state


@pytest.mark.parametrize("final_value", ["0", ""])
def test_two_handoffs_then_one_final_optional_submission(journey, final_value):
    client, sid, fake = journey
    state = _run_to_final(journey)
    token = state["awaiting"]["token"]
    response = client.post(f"/api/sessions/{sid}/submit", json={
        "token": token, "value": final_value,
    })
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["awaiting"] is None
    assert fake.submissions.count(("hY9HnrAz", final_value)) == 1
    completed = client.get(f"/api/sessions/{sid}/state").json()
    assert completed["status"] == "COMPLETED" and completed["awaiting"] is None
    assert completed["result"]["outcome"] == "completed"
    assert completed["answered_count"] == 11
    assert len(completed["auto_answered"]) == 9
    # Duplicate HTTP requests, even with a stale token, cannot re-submit an
    # already accepted update or create an additional automatic answer.
    repeated = client.post(f"/api/sessions/{sid}/submit", json={
        "token": token, "value": final_value,
    })
    assert repeated.status_code == 200
    assert len(fake.submissions) == 11


def test_accepted_input_with_old_then_empty_awaiting_is_pending_not_new_question(journey, monkeypatch):
    client, sid, fake = journey
    # Jump to the final question via the real compiled graph and fake transport.
    fake.position = 10
    old = fake.awaiting()
    fake.old_queries = 0
    original_wait = api._wait_for_workflow_progress

    async def short_wait(**kwargs):
        return await original_wait(**kwargs, timeout_seconds=0.001, poll_interval=0.01)

    monkeypatch.setattr(api, "_wait_for_workflow_progress", short_wait)
    fake.old_queries = 5
    submitted = client.post(f"/api/sessions/{sid}/submit", json={
        "token": old["token"], "value": "0",
    })
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "ADVANCING"
    assert submitted.json()["awaiting"] is None
    assert len(fake.submissions) == 1
    pending = client.get(f"/api/sessions/{sid}/state").json()
    assert pending["status"] == "ADVANCING" and pending["awaiting"] is None
    again = client.post(f"/api/sessions/{sid}/submit", json={
        "token": old["token"], "value": "0",
    })
    assert again.status_code == 200
    assert len(fake.submissions) == 1
    for _ in range(12):
        current = client.get(f"/api/sessions/{sid}/state").json()
        if current["status"] == "COMPLETED":
            break
    assert current["status"] == "COMPLETED"
    assert len(fake.submissions) == 1


def test_rejected_input_does_not_advance_or_count(journey):
    client, sid, fake = journey
    fake.reject_next = True
    response = client.post(f"/api/sessions/{sid}/submit", json={
        "token": "token-1", "value": "synthetic-invalid",
    })
    assert response.status_code == 400
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["awaiting"]["token"] == "token-1"
    assert state["answered_count"] == 0
    assert state["auto_answered"] == []


def test_confirm_policy_counts_accepted_but_not_automatic_answers(journey):
    from forms_frontend.api.sessions import InteractionPolicy

    client, sid, fake = journey
    session = api.store.get(sid)
    session.policy = InteractionPolicy.CONFIRM
    session.pending_proposal = {
        "token": fake.awaiting()["token"], "state_id": fake.awaiting()["state_id"],
        "question_text": fake.awaiting()["prompt"], "has_answer": True,
        "value": "synthetic-confirmed", "explanation": "Proposal accepted by user",
    }
    confirmed = client.post(f"/api/sessions/{sid}/confirm-proposal")
    assert confirmed.status_code == 200
    assert confirmed.json()["awaiting"]["token"] == "token-2"
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["answered_count"] == 1
    assert state["auto_answered"] == []
    assert len(fake.submissions) == 1
    assert client.get(f"/api/sessions/{sid}/auto-progress").status_code == 409


def test_sse_does_not_call_intermediate_empty_state_completion(journey, monkeypatch):
    client, sid, fake = journey
    original_wait = api._wait_for_workflow_progress

    async def short_wait(**kwargs):
        # Force the update's old-token/gap window to outlast the stream's wait.
        fake.old_queries = 5
        return await original_wait(**kwargs, timeout_seconds=0.001, poll_interval=0.01)

    monkeypatch.setattr(api, "_wait_for_workflow_progress", short_wait)
    events = _events(client.get(f"/api/sessions/{sid}/auto-progress"))
    assert [event["type"] for event in events] == ["waiting", "step", "done"]
    assert events[-1]["reason"] == "pending", events
    assert len(fake.submissions) == 1
    assert len(api.store.get(sid).auto_answered) == 1

    for _ in range(12):
        current = client.get(f"/api/sessions/{sid}/state").json()
        if current["status"] == "RUNNING" and current["awaiting"]:
            break
    assert current["awaiting"]["token"] == "token-2"
    assert len(current["auto_answered"]) == 1
    assert current["answered_count"] == 1
