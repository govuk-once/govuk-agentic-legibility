"""Tests for the Forms description generator.

Bedrock is replaced with a fake Converse client — no AWS access required.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from forms_search import enrich
from forms_search.form_text import render_form, similar_titles, source_hash


def make_form(fid: int, title: str, *, exit_page: bool = False) -> dict:
    routing = []
    if exit_page:
        routing = [
            {
                "answer_value": "No",
                "exit_page_heading": "You cannot use this form",
                "exit_page_markdown": "You must live in England.",
            }
        ]
    return {
        "form_id": fid,
        "content": {
            "name": f" {title}",
            "form_slug": title.lower().replace(" ", "-"),
            "payment_url": None,
            "steps": [
                {
                    "position": 2,
                    "data": {
                        "question_text": "What is your claim reference?",
                        "answer_type": "text",
                        "hint_text": "For example LN123",
                        "is_optional": False,
                    },
                    "routing_conditions": [],
                },
                {
                    "position": 1,
                    "data": {
                        "question_text": "Do you live in England?",
                        "answer_type": "selection",
                        "page_heading": "Before you start",
                        "guidance_markdown": "Have your claim to hand.",
                        "answer_settings": {
                            "selection_options": [{"name": "Yes"}, {"name": "No"}]
                        },
                    },
                    "routing_conditions": routing,
                },
            ],
            "what_happens_next_markdown": "We will update your claim.",
        },
    }


def ok_response(text: str) -> dict:
    return {
        "stopReason": "end_turn",
        "output": {"message": {"content": [{"reasoningContent": {}}, {"text": text}]}},
        "usage": {"inputTokens": 100, "outputTokens": 20},
    }


def throttle() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "Converse"
    )


class FakeClient:
    """Returns queued responses (or raises queued exceptions) per call."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests: list[dict] = []
        self.lock = threading.Lock()

    def converse(self, **kwargs):
        with self.lock:
            self.requests.append(kwargs)
            outcome = (
                self.outcomes.pop(0)
                if self.outcomes
                else ok_response("Amend an existing claim.")
            )
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


SETTINGS = enrich.Settings(model_id="test-model", effort="low", max_retries=3)


def no_sleep(_seconds: float) -> None:
    pass


# =====================================================================
# Rendering
# =====================================================================


def test_render_orders_questions_and_keeps_user_facing_content():
    text = render_form(make_form(6, "Amend my claim", exit_page=True))

    assert text.startswith("Title: Amend my claim\nForm ID: 6")
    assert text.index("Do you live in England?") < text.index(
        "What is your claim reference?"
    )
    assert "Options: Yes; No" in text
    assert "Hint: For example LN123" in text
    assert "Have your claim to hand." in text
    assert "user exits the form: You cannot use this form" in text
    assert "We will update your claim." in text


def test_similar_titles_finds_sibling_forms():
    titles = {
        "6": "Amend my claim for holiday pay accrued",
        "232": "Amend my claim for holiday taken but not paid",
        "9": "Register a fishing vessel",
    }
    assert similar_titles("6", titles) == [
        "Amend my claim for holiday taken but not paid"
    ]


def test_source_hash_changes_with_content():
    form = make_form(6, "Amend my claim")
    before = source_hash(form)
    form["content"]["steps"][0]["data"]["hint_text"] = "changed"
    assert source_hash(form) != before


# =====================================================================
# Model calls and retries
# =====================================================================


def test_call_model_sends_effort_and_strips_quotes():
    client = FakeClient(ok_response('  "Amend an existing\nredundancy claim."  '))

    text, usage = enrich.call_model(client, SETTINGS, "prompt")

    assert text == "Amend an existing redundancy claim."
    assert usage["outputTokens"] == 20
    request = client.requests[0]
    assert request["modelId"] == "test-model"
    assert request["additionalModelRequestFields"] == {
        "output_config": {"effort": "low"}
    }
    assert "temperature" not in request["inferenceConfig"]


def test_effort_can_be_omitted():
    client = FakeClient()
    enrich.call_model(
        client, enrich.Settings(model_id="m", effort=None, max_retries=0), "prompt"
    )
    assert "additionalModelRequestFields" not in client.requests[0]


def test_retries_throttling_then_succeeds():
    client = FakeClient(throttle(), throttle(), ok_response("Amend a claim."))
    delays = []

    text, _, attempts = enrich.generate_with_retries(
        client, SETTINGS, "prompt", sleep=delays.append
    )

    assert text == "Amend a claim."
    assert attempts == 3
    assert len(delays) == 2


def test_retries_overlong_description():
    client = FakeClient(ok_response("word " * 80), ok_response("Amend a claim."))
    text, _, attempts = enrich.generate_with_retries(
        client, SETTINGS, "prompt", sleep=no_sleep
    )
    assert (text, attempts) == ("Amend a claim.", 2)


def test_gives_up_after_max_retries():
    client = FakeClient(*[throttle()] * 4)
    with pytest.raises(enrich.RetryableError):
        enrich.generate_with_retries(client, SETTINGS, "prompt", sleep=no_sleep)
    assert len(client.requests) == 4


def test_non_retryable_error_is_raised_immediately():
    error = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "bad model"}}, "Converse"
    )
    client = FakeClient(error)
    with pytest.raises(ClientError):
        enrich.generate_with_retries(client, SETTINGS, "prompt", sleep=no_sleep)
    assert len(client.requests) == 1


# =====================================================================
# End-to-end run, resume and catalogue
# =====================================================================


@pytest.fixture
def forms_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "forms_export"
    directory.mkdir()
    for fid, title in [
        (6, "Amend my claim for holiday pay accrued"),
        (232, "Amend my claim for holiday taken but not paid"),
        (9, "Register a fishing vessel"),
    ]:
        (directory / f"{fid}.json").write_text(json.dumps(make_form(fid, title)))
    return directory


def run_main(
    monkeypatch, forms_dir: Path, out_dir: Path, client: FakeClient, *extra: str
) -> int:
    monkeypatch.setattr(
        enrich, "make_bedrock_client", lambda region, concurrency: client
    )
    return enrich.main(
        [
            "--forms-dir",
            str(forms_dir),
            "--out-dir",
            str(out_dir),
            "--model-id",
            "test-model",
            "--concurrency",
            "2",
            *extra,
        ]
    )


def test_run_writes_cache_and_catalogue(monkeypatch, forms_dir, tmp_path):
    out_dir = tmp_path / "out"
    client = FakeClient()

    assert run_main(monkeypatch, forms_dir, out_dir, client) == 0

    catalogue = json.loads((out_dir / "catalogue.json").read_text())
    assert [w["workflow_id"] for w in catalogue["workflows"]] == ["6", "9", "232"]
    assert catalogue["workflows"][0] == {
        "workflow_id": "6",
        "title": "Amend my claim for holiday pay accrued",
        "description": "Amend an existing claim.",
        "form_slug": "amend-my-claim-for-holiday-pay-accrued",
        "model_id": "test-model",
        "prompt_version": enrich.PROMPT_VERSION,
    }
    assert catalogue["missing_descriptions"] == []
    # Similar Forms are offered to the model so it can distinguish them.
    prompt_for_6 = next(
        r
        for r in client.requests
        if "Form ID: 6\n" in r["messages"][0]["content"][0]["text"]
    )
    assert (
        "- Amend my claim for holiday taken but not paid"
        in prompt_for_6["messages"][0]["content"][0]["text"]
    )


def test_resume_skips_completed_forms(monkeypatch, forms_dir, tmp_path):
    out_dir = tmp_path / "out"
    run_main(monkeypatch, forms_dir, out_dir, FakeClient(), "--ids", "6")

    second = FakeClient()
    assert run_main(monkeypatch, forms_dir, out_dir, second) == 0

    assert len(second.requests) == 2
    assert len(json.loads((out_dir / "catalogue.json").read_text())["workflows"]) == 3


def test_changed_form_or_force_regenerates(monkeypatch, forms_dir, tmp_path):
    out_dir = tmp_path / "out"
    run_main(monkeypatch, forms_dir, out_dir, FakeClient())

    form = json.loads((forms_dir / "9.json").read_text())
    form["content"]["what_happens_next_markdown"] = "Something new."
    (forms_dir / "9.json").write_text(json.dumps(form))
    changed = FakeClient()
    run_main(monkeypatch, forms_dir, out_dir, changed)
    assert len(changed.requests) == 1

    forced = FakeClient()
    run_main(monkeypatch, forms_dir, out_dir, forced, "--force", "--ids", "6")
    assert len(forced.requests) == 1


def test_failures_are_reported_and_retried_next_run(monkeypatch, forms_dir, tmp_path):
    out_dir = tmp_path / "out"
    failing = FakeClient(*[throttle()] * 7)  # exhausts retries for exactly one Form
    monkeypatch.setattr(enrich.time, "sleep", no_sleep)

    assert run_main(monkeypatch, forms_dir, out_dir, failing, "--concurrency", "1") == 1
    catalogue = json.loads((out_dir / "catalogue.json").read_text())
    assert len(catalogue["missing_descriptions"]) == 1

    assert run_main(monkeypatch, forms_dir, out_dir, FakeClient()) == 0
    assert (
        json.loads((out_dir / "catalogue.json").read_text())["missing_descriptions"]
        == []
    )


def test_truncated_cache_line_is_ignored(tmp_path):
    cache = tmp_path / "descriptions.jsonl"
    cache.write_text('{"form_id": "6", "description": "x"}\n{"form_id": "23')
    assert list(enrich.load_cache(cache)) == ["6"]
