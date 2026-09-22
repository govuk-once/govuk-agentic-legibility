"""No Temporal/AWS required: validate real SFSM models and execute real predicates."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forms_adapter import UnsupportedForm, compile_form, normalise_form
from forms_adapter.preview import PreviewRun, create_app
from src.model import SFSMDefinition
from src.predicates import evaluate

FIXTURES = Path(__file__).parent / "fixtures"


def export(form_id: str) -> dict:
    return json.loads((FIXTURES / f"{form_id}.json").read_text(encoding="utf-8"))


def compiled(form_id: str) -> SFSMDefinition:
    return SFSMDefinition.model_validate(compile_form(export(form_id)))


def start(form_id: str) -> PreviewRun:
    definition = compiled(form_id)
    return PreviewRun(definition, definition.processes[definition.entry].start)


def answer(run: PreviewRun, expected_id: str, value):
    current = run.current()
    assert current["interaction"]["id"] == expected_id
    return run.submit(value)


def test_normalisation_accepts_both_question_variants():
    for form_id, kind, count in (("6", "question_page", 11), ("2130", "question", 9)):
        content, questions = normalise_form(export(form_id))
        assert len(questions) == count
        assert questions[0].id == content["start_page"]
        assert {step["type"] for step in content["steps"]} == {kind}


@pytest.mark.parametrize("form_id", ["6", "2130"])
def test_actual_model_validates_all_states_and_transitions(form_id):
    definition = compiled(form_id)
    assert definition.schema_ == "sfsm/0.2"
    assert definition.entry == "main"
    process = definition.processes["main"]
    for sid, state in process.states.items():
        if state.type == "input":
            assert state.next in process.states, sid
            assert state.schema_.kind in {"string", "select_one", "select_many"}
        elif state.type == "choice":
            assert state.default in process.states
            assert all(rule.next in process.states for rule in state.rules)
        else:
            assert state.type == "end"
    assert definition.defaults["forms"]["preview_only"] is True


def test_linear_form_6_preserves_content_and_can_finish():
    definition = compiled("6")
    process = definition.processes["main"]
    assert process.start == "uyQrCFqM"
    assert process.states["uyQrCFqM"].schema_.model_extra["presentation"]["guidance_markdown"].startswith("## Part 1")
    assert process.states["uyQrCFqM"].schema_.model_extra["presentation"]["answer_settings"]["input_type"] == "first_and_last_name"
    assert process.states["uyQrCFqM"].next == "nK3iWXxs"
    assert process.states["v2rxCDt3"].next == "v2rxCDt3__address_line_2"
    assert len([s for s in process.states.values() if s.type == "input"]) == 14
    run = start("6")
    # 11 original questions, plus 3 extra address fields; name is one string.
    for sid, value in [
        ("uyQrCFqM", "Alex Example"),
        ("nK3iWXxs", "LN00000000"), ("opyfSJWo", "QQ000000C"),
        ("ywWSZiYg", "alex@example.invalid"), ("8FTw3t4z", "2000-01-02"),
        ("v2rxCDt3", "1 Sample Street"), ("v2rxCDt3__address_line_2", ""),
        ("v2rxCDt3__town_or_city", "London"), ("v2rxCDt3__postcode", "SW1A 1AA"),
        ("wWPXauTh", "Synthetic Ltd"), ("B9LuEbyQ", ""),
        ("VRYgtG3z", ""), ("gV9s3nJy", ""), ("hY9HnrAz", ""),
    ]:
        response = answer(run, sid, value)
    assert response["terminal"]
    assert response["answers"]["uyQrCFqM"] == "Alex Example"
    assert response["answers"]["v2rxCDt3"]["town_or_city"] == "London"
    assert response["answers"]["B9LuEbyQ"] == ""


@pytest.mark.parametrize("input_type,title_needed", [
    ("full_name", "false"),
    ("first_and_last_name", "false"),
    ("first_and_last_name", "true"),
    ("full_name", "true"),
    ("first_middle_and_last_name", "false"),
    ("first_middle_and_last_name", "true"),
])
def test_name_variants_use_one_string_and_preserve_settings(input_type, title_needed):
    fixture = export("6")
    name = fixture["content"]["steps"][0]
    settings = {"input_type": input_type, "title_needed": title_needed}
    name["data"]["answer_settings"] = settings

    definition = SFSMDefinition.model_validate(compile_form(fixture))
    states = definition.processes["main"].states
    state = states[name["id"]]
    assert state.schema_.kind == "string"
    assert state.assign == f"answers.{name['id']}"
    assert state.next == "nK3iWXxs"
    assert state.schema_.model_extra["presentation"]["answer_settings"] == settings
    assert not any(sid.startswith(f"{name['id']}__") for sid in states)

    run = PreviewRun(definition, definition.processes["main"].start)
    response = answer(run, name["id"], "Dr Alex Example")
    assert response["interaction"]["id"] == "nK3iWXxs"
    assert response["answers"][name["id"]] == "Dr Alex Example"


def test_optional_name_can_be_skipped():
    fixture = export("6")
    name = fixture["content"]["steps"][0]
    name["data"]["is_optional"] = True
    name["data"]["answer_settings"] = {"input_type": "full_name", "title_needed": "true"}
    definition = SFSMDefinition.model_validate(compile_form(fixture))
    assert definition.processes["main"].states[name["id"]].schema_.allow_skip is True
    run = PreviewRun(definition, definition.processes["main"].start)
    assert answer(run, name["id"], None)["answers"][name["id"]] == ""


def _first_four(run: PreviewRun, assistance: str):
    answer(run, "Z9qiMdb6", "I'm using this service as a member of the public")
    answer(run, "NeNd3HYi", "Satisfied")
    answer(run, "oygaerZY", "Some sample feedback")
    return answer(run, "mq4KgkUb", assistance)


def test_2130_no_skips_all_assistance_questions():
    run = start("2130")
    result = _first_four(run, "No")
    assert result["interaction"]["id"] == "31pMZdRv"
    assert "bKCtg9gW" not in result["answers"]
    assert answer(run, "31pMZdRv", "")["terminal"]


def test_2130_friend_skips_satisfaction_and_improvement():
    run = start("2130")
    _first_four(run, "Yes")
    answer(run, "bKCtg9gW", "Sample help")
    result = answer(run, "dKg1ApnD", "A friend, relative or work colleague")
    assert result["interaction"]["id"] == "31pMZdRv"
    assert "5ocPRG9b" not in result["answers"]
    assert answer(run, "31pMZdRv", "sample@example.invalid")["terminal"]


def test_2130_default_routes_through_assistance_questions():
    run = start("2130")
    _first_four(run, "Yes")
    answer(run, "bKCtg9gW", "Sample help")
    result = answer(run, "dKg1ApnD", "HM Land Registry")
    assert result["interaction"]["id"] == "5ocPRG9b"
    answer(run, "5ocPRG9b", "Very satisfied")
    answer(run, "giCnMGtq", "No improvements")
    assert answer(run, "31pMZdRv", "")["terminal"]


def test_2130_optional_choice_has_explicit_skip_supported_by_preview():
    definition = compiled("2130")
    schema = definition.processes["main"].states["dKg1ApnD"].schema_
    assert schema.allow_skip is True
    assert {opt.value for opt in schema.options} >= {"__forms_skip__", "HM Land Registry"}
    run = start("2130")
    _first_four(run, "Yes")
    answer(run, "bKCtg9gW", "Test")
    assert answer(run, "dKg1ApnD", None)["interaction"]["id"] == "5ocPRG9b"


def test_real_predicates_used_by_branches():
    rules = compiled("2130").processes["main"].states["mq4KgkUb__route"].rules
    assert evaluate(rules[0].when, {"answers": {"mq4KgkUb": "No"}})
    assert not evaluate(rules[0].when, {"answers": {"mq4KgkUb": "Yes"}})


def test_multi_select_contains_and_skip_to_end():
    fixture = export("2130")
    first = fixture["content"]["steps"][0]
    first["data"]["answer_settings"]["only_one_option"] = "false"
    first["routing_conditions"] = [{"answer_value": "I'm using this service as a member of the public",
                                     "skip_to_end": True, "goto_page_id": None}]
    definition = SFSMDefinition.model_validate(compile_form(fixture))
    choice = definition.processes["main"].states["Z9qiMdb6__route"]
    assert choice.rules[0].when["op"] == "contains"
    run = PreviewRun(definition, definition.processes["main"].start)
    assert answer(run, "Z9qiMdb6", ["I'm using this service as a member of the public"])["terminal"]


@pytest.mark.parametrize("mutation,reason", [
    (lambda f: f["content"]["steps"][0]["data"].update(is_repeatable=True), "repeatable"),
    (lambda f: f["content"]["steps"][0].update(exit_pages=[{"id": 1}]), "exit_pages"),
    (lambda f: f["content"]["steps"][0]["data"].update(answer_type="file"), "file"),
    (lambda f: f["content"].update(payment_url="https://payment.invalid"), "payment"),
    (lambda f: f["content"]["steps"][0].update(next_step_id="unknown"), "unknown"),
    (lambda f: f["content"]["steps"][3]["routing_conditions"][0].update(goto_page_id="unknown"), "unknown"),
    (lambda f: f["content"]["steps"][3]["routing_conditions"][0].update(check_page_id="Z9qiMdb6"), "cross-page"),
])
def test_unsupported_features_reported(mutation, reason):
    fixture = copy.deepcopy(export("2130"))
    mutation(fixture)
    with pytest.raises(UnsupportedForm, match=reason):
        compile_form(fixture)


def test_batch_compilation_continues_past_unsupported(tmp_path):
    source = tmp_path / "exports"
    output = tmp_path / "compiled"
    source.mkdir()
    for form_id in ("6", "2130"):
        (source / f"{form_id}.json").write_text((FIXTURES / f"{form_id}.json").read_text())
    bad = export("6")
    bad["content"]["steps"][0]["data"]["is_repeatable"] = True
    (source / "bad.json").write_text(json.dumps(bad))
    report = tmp_path / "report.json"
    result = subprocess.run([sys.executable, "-m", "forms_adapter", "--batch", str(source),
                             "--output", str(output), "--report", str(report)],
                            capture_output=True, text=True, cwd=FIXTURES.parents[2])
    assert result.returncode == 0, result.stderr
    assert "Compiled 2/3" in result.stdout
    assert {path.name for path in output.iterdir()} == {"6.json", "2130.json"}
    assert [r["status"] for r in json.loads(report.read_text())].count("unsupported") == 1


def test_web_preview_uses_compiled_sfms_without_agent(tmp_path):
    (tmp_path / "2130.json").write_text(json.dumps(compile_form(export("2130"))))
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/forms").json()[0]["id"] == "2130"
    assert client.post("/api/forms/../../runs").status_code in (404, 405)
    response = client.post("/api/forms/2130/runs").json()
    assert response["interaction"]["id"] == "Z9qiMdb6"
    run_id = response["run_id"]
    url = f"/api/forms/runs/{run_id}/answers"
    assert client.post(url, json={"answer": "not an option"}).status_code == 422
    for value in ("I'm using this service as a member of the public", "Satisfied", "Feedback", "No"):
        response = client.post(url, json={"answer": value}).json()
    assert response["interaction"]["id"] == "31pMZdRv"
    assert client.post(url, json={"answer": None}).json()["terminal"] is True
    assert client.post(url, json={"answer": "extra"}).status_code == 422
