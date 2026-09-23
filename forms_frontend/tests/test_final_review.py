"""Final review on the real compiled form-6 graph, with Temporal transport mocked.

Agent and workflow transport are fake; all eleven state IDs, schemas and
transitions come from the exported Form compiled by the production adapter.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from forms_frontend.api import main as api
from forms_frontend.api.sessions import SessionStore
from forms_frontend.tests.test_completion_handoffs import LinearTemporal, _events


class ReplacementRun(LinearTemporal):
    async def submit(self, *, token, value, **kwargs):
        if value == "INVALID":
            raise ValueError("Edited value failed validation")
        return await super().submit(token=token, value=value, **kwargs)

    async def cancel(self):
        self.cancelled = True


class ReviewTransport:
    """Independent Temporal executions, each using the real compiled input path."""

    def __init__(self, definition):
        self.definition = definition
        self.executions = {"initial-run": ReplacementRun(definition)}
        self.started = []

    async def start_workflow(self, *args, **kwargs):
        run_id = kwargs.get("id", "initial-run")
        if run_id != "initial-run":
            self.executions[run_id] = ReplacementRun(kwargs["arg"])
            self.started.append((run_id, kwargs["arg"]))
        return SimpleNamespace(id=run_id)

    async def state(self, *, workflow_id, **kwargs):
        return await self.executions[workflow_id].state()

    async def submit(self, *, workflow_id, token, value, **kwargs):
        return await self.executions[workflow_id].submit(token=token, value=value)

    def get_workflow_handle(self, workflow_id):
        return self.executions[workflow_id]


@pytest.fixture
def review_journey(monkeypatch, form_6_definition):
    transport = ReviewTransport(form_6_definition)
    fixture = json.loads((Path(__file__).parent.parent / "fixtures" /
                          "form_6_partial_details.json").read_text())

    async def get_definition(**kwargs):
        return form_6_definition

    async def start(**kwargs):
        return "initial-run"

    async def get_temporal():
        return transport

    async def propose(*, awaiting, conversation_history):
        assert conversation_history == fixture["conversation"]
        index = next(i for i, (state_id, _) in enumerate(
            transport.executions["initial-run"].questions)
            if state_id == awaiting["state_id"])
        if index in (7, 10):
            return {"has_answer": False, "value": None, "explanation": "Needs user"}
        return {"has_answer": True, "value": f"synthetic-{index}", "explanation": "Fixture"}

    monkeypatch.setattr(api, "store", SessionStore())
    monkeypatch.setattr(api, "get_temporal_client", get_temporal)
    monkeypatch.setattr(api, "get_http_client", get_temporal)
    monkeypatch.setattr(api.tool_functions, "get_workflow_definition", get_definition)
    monkeypatch.setattr(api.tool_functions, "start_workflow", start)
    monkeypatch.setattr(api.tool_functions, "get_workflow_state", transport.state)
    monkeypatch.setattr(api.tool_functions, "submit_input", transport.submit)
    monkeypatch.setattr(api, "propose_answer", propose)

    with TestClient(api.app) as client:
        started = client.post("/api/sessions", json={
            "form_id": "6", "policy": "auto", "review_before_submit": True,
            "fixture_id": fixture["id"],
        })
        assert started.status_code == 200, started.text
        yield client, started.json()["session_id"], transport


def reach_final_review(journey, final_answer="0"):
    client, sid, transport = journey
    first = _events(client.get(f"/api/sessions/{sid}/auto-progress"))
    assert len([e for e in first if e["type"] == "step"]) == 7
    assert first[-1]["reason"] == "needs_input"
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["awaiting"]["state_id"] == "B9LuEbyQ"
    assert len(state["answer_history"]) == 7
    manual = client.post(f"/api/sessions/{sid}/submit", json={
        "token": state["awaiting"]["token"], "value": "01/01/2026",
    })
    assert manual.status_code == 200, manual.text
    second = _events(client.get(f"/api/sessions/{sid}/auto-progress"))
    assert len([e for e in second if e["type"] == "step"]) == 2
    assert second[-1]["reason"] == "needs_input"
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["awaiting"]["state_id"] == "hY9HnrAz"
    assert len(state["answer_history"]) == 10
    final = client.post(f"/api/sessions/{sid}/submit", json={
        "token": state["awaiting"]["token"], "value": final_answer,
    })
    assert final.status_code == 200, final.text
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["status"] == "COMPLETED" and state["awaiting"] is None
    assert state["review_required"] is True and state["review_confirmed"] is False
    assert state["review_before_submit"] is True
    assert state["answered_count"] == len(state["answer_history"]) == 11
    assert len(state["auto_answered"]) == 9
    assert state["answer_history"][7]["source"] == "manual"
    assert state["answer_history"][10]["value"] == final_answer
    assert transport.executions["initial-run"].submissions[-1] == ("hY9HnrAz", final_answer)
    return state


@pytest.mark.parametrize("final_answer", ["0", ""])
def test_form6_auto_two_handoffs_final_review_before_accept(review_journey, final_answer):
    client, sid, transport = review_journey
    state = reach_final_review(review_journey, final_answer)
    assert state["answer_history"][10]["source"] == "manual"
    initial = transport.executions["initial-run"]
    assert len(initial.submissions) == 11  # one final Continue/Skip
    assert client.post(f"/api/sessions/{sid}/review/confirm").json() == {
        "review_confirmed": True,
    }
    assert client.post(f"/api/sessions/{sid}/review/confirm").json() == {
        "review_confirmed": True,
    }  # double-click safe
    finished = client.get(f"/api/sessions/{sid}/state").json()
    assert finished["review_required"] is False and finished["review_confirmed"] is True
    assert len(initial.submissions) == 11  # reviewing never resubmits an input


def test_edit_final_zero_revalidates_once_in_fresh_temporal_run(review_journey):
    client, sid, transport = review_journey
    before = reach_final_review(review_journey)
    edited = client.post(f"/api/sessions/{sid}/review/amend", json={
        "index": 10, "state_id": "hY9HnrAz", "value": "4", "revision": 0,
    })
    assert edited.status_code == 200, edited.text
    state = edited.json()
    assert state["status"] == "COMPLETED" and state["review_required"]
    assert state["review_revision"] == 1
    assert state["workflow_id"] != before["workflow_id"]
    assert state["answer_history"][10]["value"] == "4"
    assert len(state["auto_answered"]) == 9
    assert len(state["answer_history"]) == 11
    assert len(transport.started) == 1
    assert transport.started[0][1] == api.store.get(sid).definition
    assert len(transport.executions["initial-run"].submissions) == 11
    assert len(transport.executions[state["workflow_id"]].submissions) == 11
    assert transport.executions[state["workflow_id"]].submissions[-1] == ("hY9HnrAz", "4")
    assert client.post(f"/api/sessions/{sid}/review/amend", json={
        "index": 10, "state_id": "hY9HnrAz", "value": "5", "revision": 0,
    }).status_code == 409  # an out-of-date second click cannot replay again
    assert client.post(f"/api/sessions/{sid}/review/confirm").status_code == 200


def test_edit_automatic_answer_is_now_manual_and_cumulative_count_falls(review_journey):
    client, sid, _ = review_journey
    reach_final_review(review_journey)
    edited = client.post(f"/api/sessions/{sid}/review/amend", json={
        "index": 8, "state_id": "VRYgtG3z", "value": "30", "revision": 0,
    })
    assert edited.status_code == 200, edited.text
    state = edited.json()
    assert state["answer_history"][8]["source"] == "manual"
    assert state["answer_history"][8]["value"] == "30"
    assert len(state["auto_answered"]) == 8
    assert state["answered_count"] == 11 and state["review_required"]


def test_invalid_edit_does_not_change_original_completed_workflow(review_journey):
    client, sid, transport = review_journey
    before = reach_final_review(review_journey)
    response = client.post(f"/api/sessions/{sid}/review/amend", json={
        "index": 10, "state_id": "hY9HnrAz", "value": "INVALID", "revision": 0,
    })
    assert response.status_code == 422
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["workflow_id"] == before["workflow_id"]
    assert state["answer_history"][10]["value"] == "0"
    assert state["review_required"] and state["review_revision"] == 0
    assert len(transport.executions["initial-run"].submissions) == 11
    new_id, _ = transport.started[-1]
    assert transport.executions[new_id].cancelled is True


def test_no_replay_for_same_value_and_no_review_without_opt_in(review_journey):
    client, sid, transport = review_journey
    reach_final_review(review_journey)
    original = client.get(f"/api/sessions/{sid}/state").json()
    no_change = client.post(f"/api/sessions/{sid}/review/amend", json={
        "index": 10, "state_id": "hY9HnrAz", "value": "0", "revision": 0,
    })
    assert no_change.status_code == 200 and no_change.json()["workflow_id"] == original["workflow_id"]
    assert transport.started == []
    # If review was switched off, an already completed form remains complete.
    off = client.put(f"/api/sessions/{sid}/policy", json={
        "policy": "auto", "review_before_submit": False,
    })
    assert off.status_code == 200
    assert client.get(f"/api/sessions/{sid}/state").json()["review_required"] is False
    assert client.post(f"/api/sessions/{sid}/review/confirm").status_code == 409


def test_review_is_not_offered_for_journeys_with_external_actions(api_client, form_2130_definition):
    # Avoid replay of potentially non-idempotent departmental service actions.
    from unittest.mock import patch
    unsafe = json.loads(json.dumps(form_2130_definition))
    unsafe["processes"]["main"]["states"]["side_effect"] = {"type": "action"}
    with patch("agent.tools.get_workflow_definition", return_value=unsafe):
        response = api_client.post("/api/sessions", json={
            "form_id": "2130", "policy": "auto", "review_before_submit": True,
        })
    assert response.status_code == 422


class BranchingRun:
    """Minimal transport exercising the real form-2130 compiled choice rules."""

    def __init__(self, definition):
        main = definition["processes"]["main"]
        self.states = main["states"]
        self.current_id = main["start"]
        self.values = {}
        self.submissions = []
        self.counter = 0
        self.pending = False
        self.old_queries = 0
        self.gap_queries = 0

    def awaiting(self):
        state = self.states[self.current_id]
        if state["type"] == "end":
            return None
        assert state["type"] == "input"
        return {
            "token": f"graph-token-{self.counter}", "state_id": self.current_id,
            "prompt": state["prompt"], "schema": state["schema"],
        }

    def current(self):
        return {"status": "COMPLETED" if self.awaiting() is None else "RUNNING",
                "awaiting": self.awaiting(), "transcript": []}

    def advance(self):
        self.current_id = self.states[self.current_id]["next"]
        while self.states[self.current_id]["type"] in ("choice", "output"):
            node = self.states[self.current_id]
            if node["type"] == "output":
                self.current_id = node["next"]
                continue
            dest = node["default"]
            for rule in node["rules"]:
                pred = rule["when"]
                key = pred["path"].removeprefix("answers.")
                value = self.values.get(key)
                matched = (pred["op"] == "is_false" and value is False)
                matched |= (pred["op"] == "eq" and value == pred.get("value"))
                if matched:
                    dest = rule["next"]
                    break
            self.current_id = dest
        self.counter += 1

    async def state(self):
        if self.pending:
            if self.old_queries:
                self.old_queries -= 1
                return self.current()
            if self.gap_queries:
                self.gap_queries -= 1
                return {"status": "RUNNING", "awaiting": None, "transcript": []}
            self.pending = False
            self.advance()
        return self.current()

    async def submit(self, *, token, value):
        assert not self.pending
        assert self.awaiting()["token"] == token
        self.values[self.current_id] = value
        self.submissions.append((self.current_id, value))
        self.pending = True
        self.old_queries = 1
        self.gap_queries = 1
        return self.current()

    async def result(self):
        return {"status": "complete", "outcome": "form_answers_collected"}

    async def cancel(self):
        self.cancelled = True


class BranchingTransport:
    def __init__(self, definition):
        self.executions = {"branch-original": BranchingRun(definition)}

    async def start_workflow(self, *args, **kwargs):
        run_id = kwargs["id"]
        self.executions[run_id] = BranchingRun(kwargs["arg"])
        return SimpleNamespace(id=run_id)

    async def state(self, *, workflow_id, **kwargs):
        return await self.executions[workflow_id].state()

    async def submit(self, *, workflow_id, token, value, **kwargs):
        return await self.executions[workflow_id].submit(token=token, value=value)

    def get_workflow_handle(self, workflow_id):
        return self.executions[workflow_id]


def test_changed_branch_invalidates_downstream_answers_and_requests_input(monkeypatch, form_2130_definition):
    transport = BranchingTransport(form_2130_definition)

    async def get_temporal():
        return transport

    async def get_definition(**kwargs):
        return form_2130_definition

    async def initial_start(**kwargs):
        return "branch-original"

    monkeypatch.setattr(api, "store", SessionStore())
    monkeypatch.setattr(api, "get_temporal_client", get_temporal)
    monkeypatch.setattr(api, "get_http_client", get_temporal)
    monkeypatch.setattr(api.tool_functions, "get_workflow_definition", get_definition)
    monkeypatch.setattr(api.tool_functions, "start_workflow", initial_start)
    monkeypatch.setattr(api.tool_functions, "get_workflow_state", transport.state)
    monkeypatch.setattr(api.tool_functions, "submit_input", transport.submit)

    with TestClient(api.app) as client:
        resp = client.post("/api/sessions", json={
            "form_id": "2130", "policy": "manual", "review_before_submit": True,
        })
        assert resp.status_code == 200, resp.text
        sid = resp.json()["session_id"]
        for _ in range(12):
            state = client.get(f"/api/sessions/{sid}/state").json()
            if state["status"] == "COMPLETED":
                break
            awaiting = state["awaiting"]
            if awaiting["state_id"] == "mq4KgkUb":
                answer = True
            elif awaiting["state_id"] == "dKg1ApnD":
                answer = "Someone else"  # select the branch with all nine questions
            elif awaiting["schema"]["kind"] == "select_one":
                answer = awaiting["schema"]["options"][0]["value"]
            else:
                answer = "synthetic answer"
            posted = client.post(f"/api/sessions/{sid}/submit", json={
                "token": awaiting["token"], "value": answer,
            })
            assert posted.status_code == 200, posted.text
        before = client.get(f"/api/sessions/{sid}/state").json()
        assert before["review_required"] and len(before["answer_history"]) == 9
        assert before["answer_history"][3]["state_id"] == "mq4KgkUb"

        amended = client.post(f"/api/sessions/{sid}/review/amend", json={
            "index": 3, "state_id": "mq4KgkUb", "value": False, "revision": 0,
        })
        assert amended.status_code == 200, amended.text
        new = amended.json()
        # Changed Yes -> No: compiled rules skip assistance-related questions.
        assert new["status"] == "RUNNING"
        assert new["awaiting"]["state_id"] == "31pMZdRv"
        assert new["review_replay_needs_input"] is True
        assert new["answer_history"][3]["value"] is False
        assert len(new["answer_history"]) == 4
        assert new["answered_count"] == 4 and new["review_required"] is False
        assert len(transport.executions["branch-original"].submissions) == 9

        final = client.post(f"/api/sessions/{sid}/submit", json={
            "token": new["awaiting"]["token"], "value": "email@example.org",
        })
        assert final.status_code == 200, final.text
        complete = client.get(f"/api/sessions/{sid}/state").json()
        assert complete["review_required"] is True
        assert complete["review_replay_needs_input"] is False
        assert len(complete["answer_history"]) == 5
        assert [item["state_id"] for item in complete["answer_history"]][-2:] == [
            "mq4KgkUb", "31pMZdRv",
        ]


def test_fully_automatic_form6_displays_final_review_not_first_question(review_journey, monkeypatch):
    """Regression: all 11 auto answers end on the summary, never a new form."""
    client, sid, transport = review_journey

    async def all_answers(*, awaiting, conversation_history):
        return {"has_answer": True, "value": "0" if awaiting["state_id"] == "hY9HnrAz"
                else "synthetic answer", "explanation": "Fixture"}

    monkeypatch.setattr(api, "propose_answer", all_answers)
    events = _events(client.get(f"/api/sessions/{sid}/auto-progress"))
    assert len([event for event in events if event["type"] == "step"]) == 11
    assert events[-1]["reason"] == "complete"
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["review_required"] and state["status"] == "COMPLETED"
    assert state["awaiting"] is None
    assert len(state["answer_history"]) == len(state["auto_answered"]) == 11
    assert state["answer_history"][0]["state_id"] == "uyQrCFqM"
    assert state["answer_history"][-1]["value"] == "0"
    assert len(transport.executions["initial-run"].submissions) == 11

    # The terminal observation is monotonic even when a subsequent query is
    # delayed or erroneously supplies a historical first-question snapshot.
    async def old_first_question(**kwargs):
        return {"status": "RUNNING", "awaiting": transport.executions[
            "initial-run"].awaiting(position=0), "transcript": []}

    monkeypatch.setattr(api.tool_functions, "get_workflow_state", old_first_question)
    repeat = client.get(f"/api/sessions/{sid}/state").json()
    assert repeat["status"] == "COMPLETED" and repeat["awaiting"] is None
    assert repeat["review_required"] and len(repeat["answer_history"]) == 11
    assert client.post(f"/api/sessions/{sid}/review/confirm").status_code == 200
    finished = client.get(f"/api/sessions/{sid}/state").json()
    assert finished["status"] == "COMPLETED" and not finished["review_required"]


def test_optional_final_zero_or_skip_cannot_regress_to_first_input(review_journey, monkeypatch):
    client, sid, transport = review_journey
    reach_final_review(review_journey, final_answer="")

    async def old_first_question(**kwargs):
        return {"status": "RUNNING", "awaiting": transport.executions[
            "initial-run"].awaiting(position=0), "transcript": []}

    monkeypatch.setattr(api.tool_functions, "get_workflow_state", old_first_question)
    state = client.get(f"/api/sessions/{sid}/state").json()
    assert state["status"] == "COMPLETED" and state["review_required"]
    assert state["awaiting"] is None and state["answer_history"][-1]["value"] == ""
    assert len(transport.executions["initial-run"].submissions) == 11
