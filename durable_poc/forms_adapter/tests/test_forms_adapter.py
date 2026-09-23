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
from src.model import SFSMDefinition, OutputState, EndState
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
            assert state.schema_.kind in {"string", "select_one", "select_many", "boolean", "file_ref"}
        elif state.type == "choice":
            assert state.default in process.states
            assert all(rule.next in process.states for rule in state.rules)
        elif state.type == "output":
            assert state.next in process.states
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
    assert process.states["v2rxCDt3"].next == "wWPXauTh"
    assert process.states["v2rxCDt3"].schema_.kind == "string"
    assert process.states["v2rxCDt3"].schema_.model_extra["presentation"]["answer_settings"]["input_type"]["uk_address"] == "true"
    assert len([s for s in process.states.values() if s.type == "input"]) == 11
    run = start("6")
    # Exactly one input per original question; rendering compound values belongs
    # to a Forms-aware frontend, not to the process graph.
    for sid, value in [
        ("uyQrCFqM", "Alex Example"),
        ("nK3iWXxs", "LN00000000"), ("opyfSJWo", "QQ000000C"),
        ("ywWSZiYg", "alex@example.invalid"), ("8FTw3t4z", "2000-01-02"),
        ("v2rxCDt3", "1 Sample Street, London SW1A 1AA"),
        ("wWPXauTh", "Synthetic Ltd"), ("B9LuEbyQ", ""),
        ("VRYgtG3z", ""), ("gV9s3nJy", ""), ("hY9HnrAz", ""),
    ]:
        response = answer(run, sid, value)
    assert response["terminal"]
    assert response["answers"]["uyQrCFqM"] == "Alex Example"
    assert response["answers"]["v2rxCDt3"] == "1 Sample Street, London SW1A 1AA"
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
    return answer(run, "mq4KgkUb", {"Yes": True, "No": False}.get(assistance, assistance))


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
    assert rules[0].when == {"op": "is_false", "path": "answers.mq4KgkUb"}
    assert evaluate(rules[0].when, {"answers": {"mq4KgkUb": False}})
    assert not evaluate(rules[0].when, {"answers": {"mq4KgkUb": True}})


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
    (lambda f: f["content"]["steps"][0]["data"].update(is_repeatable="yes"), "is_repeatable"),
    (lambda f: f["content"]["steps"][0].update(exit_pages=[{"id": 1}]), "exit_pages"),
    (lambda f: f["content"]["steps"][0].update(next_step_id="unknown"), "unknown"),
    (lambda f: f["content"]["steps"][3]["routing_conditions"][0].update(goto_page_id="unknown"), "unknown"),
    (lambda f: f["content"]["steps"][3]["routing_conditions"][0].update(check_page_id="dKg1ApnD"), "preceding"),
])
def test_unsupported_features_reported(mutation, reason):
    fixture = copy.deepcopy(export("2130"))
    mutation(fixture)
    with pytest.raises(UnsupportedForm, match=reason):
        compile_form(fixture)


def test_routed_yes_no_is_boolean_but_unrouted_yes_no_remains_selection():
    definition = compiled("2130")
    states = definition.processes["main"].states
    assert states["mq4KgkUb"].schema_.kind == "boolean"
    assert states["mq4KgkUb__route"].rules[0].when["op"] == "is_false"
    fixture = export("2130")
    fixture["content"]["steps"][3]["routing_conditions"] = []
    unrouted = SFSMDefinition.model_validate(compile_form(fixture))
    assert unrouted.processes["main"].states["mq4KgkUb"].schema_.kind == "select_one"


def test_scalar_questions_have_no_type_allowlist_and_preserve_source_metadata():
    fixture = export("6")
    phone = fixture["content"]["steps"][1]
    phone["data"]["answer_type"] = "phone_number"
    phone["data"]["answer_settings"] = None
    another = fixture["content"]["steps"][2]
    another["data"]["answer_type"] = "some_future_scalar"
    another["data"]["answer_settings"] = {"widget": "future"}
    states = compiled("6").processes["main"].states
    assert states["nK3iWXxs"].schema_.kind == "string"  # baseline text
    changed = SFSMDefinition.model_validate(compile_form(fixture)).processes["main"].states
    for step in (phone, another):
        state = changed[step["id"]]
        assert state.schema_.kind == "string"
        assert state.schema_.model_extra["presentation"]["answer_type"] == step["data"]["answer_type"]
        assert state.schema_.model_extra["presentation"]["answer_settings"] == step["data"]["answer_settings"]


def test_routing_on_a_generic_string_uses_native_equality():
    fixture = export("6")
    question = fixture["content"]["steps"][1]
    question["routing_conditions"] = [{"answer_value": "skip", "goto_page_id": "ywWSZiYg"}]
    definition = SFSMDefinition.model_validate(compile_form(fixture))
    route = definition.processes["main"].states["nK3iWXxs__route"]
    assert route.rules[0].when == {"op": "eq", "path": "answers.nK3iWXxs", "value": "skip"}
    run = PreviewRun(definition, definition.processes["main"].start)
    answer(run, "uyQrCFqM", "Alex Example")
    assert answer(run, "nK3iWXxs", "skip")["interaction"]["id"] == "ywWSZiYg"


def test_cross_page_routing_uses_earlier_answer_not_current_answer():
    fixture = export("2130")
    third = fixture["content"]["steps"][2]
    third["routing_conditions"] = [{
        "check_page_id": "Z9qiMdb6", "routing_page_id": third["id"],
        "answer_value": "I'm using this service as a member of the public",
        "goto_page_id": "31pMZdRv", "skip_to_end": False,
    }]
    definition = SFSMDefinition.model_validate(compile_form(fixture))
    choice = definition.processes["main"].states[f"{third['id']}__route"]
    assert choice.rules[0].when["path"] == "answers.Z9qiMdb6"
    run = PreviewRun(definition, definition.processes["main"].start)
    answer(run, "Z9qiMdb6", "I'm using this service as a member of the public")
    answer(run, "NeNd3HYi", "Satisfied")
    assert answer(run, third["id"], "Synthetic")["interaction"]["id"] == "31pMZdRv"


def test_file_question_uses_existing_file_ref_contract_and_never_uploads_bytes():
    fixture = export("6")
    question = fixture["content"]["steps"][1]
    question["data"]["answer_type"] = "file"
    question["data"]["answer_settings"] = {"max_files": 1}
    definition = SFSMDefinition.model_validate(compile_form(fixture))
    state = definition.processes["main"].states[question["id"]]
    assert state.schema_.kind == "file_ref"
    assert state.schema_.model_extra["presentation"]["answer_settings"] == {"max_files": 1}
    run = PreviewRun(definition, definition.processes["main"].start)
    answer(run, "uyQrCFqM", "Alex Example")
    assert run.current()["interaction"]["input_schema"]["properties"]["answer"]["type"] == "object"
    with pytest.raises(ValueError, match="reference"):
        answer(run, question["id"], "binary file bytes")
    answer(run, question["id"], {"ref": "synthetic-blob-1", "bytes": 128, "content_type": "application/pdf"})
    assert run.answers[question["id"]]["ref"] == "synthetic-blob-1"


def test_ambiguous_non_routed_selection_is_rejected():
    fixture = export("2130")
    first = fixture["content"]["steps"][0]
    first["data"]["answer_settings"]["only_one_option"] = None
    with pytest.raises(UnsupportedForm, match="selection needs valid options"):
        compile_form(fixture)
    routed = fixture["content"]["steps"][3]
    routed["data"]["answer_settings"]["only_one_option"] = None
    with pytest.raises(UnsupportedForm, match="selection needs valid options"):
        compile_form(fixture)


def test_null_boolean_flags_default_to_false_and_true_repeatable_is_supported():
    fixture = export("6")
    question = fixture["content"]["steps"][0]
    question["data"]["is_optional"] = None
    question["data"]["is_repeatable"] = None
    assert SFSMDefinition.model_validate(compile_form(fixture)).processes["main"].states[question["id"]].schema_.kind == "string"
    question["data"]["is_repeatable"] = True
    states = SFSMDefinition.model_validate(compile_form(fixture)).processes["main"].states
    assert states[question["id"]].next == f"{question['id']}__append"


def test_batch_compilation_continues_past_unsupported(tmp_path):
    source = tmp_path / "exports"
    output = tmp_path / "compiled"
    source.mkdir()
    for form_id in ("6", "2130"):
        (source / f"{form_id}.json").write_text((FIXTURES / f"{form_id}.json").read_text())
    bad = export("6")
    bad["content"]["steps"][0]["data"]["is_repeatable"] = True
    bad["content"]["steps"][0]["data"]["is_optional"] = True
    (source / "bad.json").write_text(json.dumps(bad))
    output.mkdir()
    (output / "bad.json").write_text("STALE UNSUPPORTED DEFINITION")
    report = tmp_path / "report.json"
    result = subprocess.run([sys.executable, "-m", "forms_adapter", "--batch", str(source),
                             "--output", str(output), "--report", str(report)],
                            capture_output=True, text=True, cwd=FIXTURES.parents[2])
    assert result.returncode == 0, result.stderr
    assert "Compiled 2/3" in result.stdout
    assert {path.name for path in output.iterdir()} == {"6.json", "2130.json"}
    assert [r["status"] for r in json.loads(report.read_text())].count("unsupported") == 1
    assert any("address collected as one string" in w
               for row in json.loads(report.read_text()) if row["status"] == "ok"
               for w in row.get("warnings", []))


def test_batch_report_warns_on_unfamiliar_type_and_file_without_rejecting(tmp_path):
    source = tmp_path / "exports"
    source.mkdir()
    fixture = export("6")
    fixture["content"]["steps"][1]["data"]["answer_type"] = "future_scalar"
    fixture["content"]["steps"][2]["data"]["answer_type"] = "file"
    (source / "6.json").write_text(json.dumps(fixture))
    report = tmp_path / "report.json"
    result = subprocess.run([sys.executable, "-m", "forms_adapter", "--batch", str(source),
                             "--output", str(tmp_path / "compiled"), "--report", str(report)],
                            capture_output=True, text=True, cwd=FIXTURES.parents[2])
    assert result.returncode == 0, result.stderr
    entry = json.loads(report.read_text())[0]
    assert entry["status"] == "preview_only"
    assert any("unrecognised answer_type 'future_scalar'" in warning for warning in entry["warnings"])
    assert any("file_ref needs an upload-capable client" in warning for warning in entry["warnings"])
    compiled_definition = SFSMDefinition.model_validate_json((tmp_path / "compiled" / "6.json").read_text())
    assert compiled_definition.processes["main"].states["opyfSJWo"].schema_.kind == "file_ref"


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
    for value in ("I'm using this service as a member of the public", "Satisfied", "Feedback", False):
        response = client.post(url, json={"answer": value}).json()
    assert response["interaction"]["id"] == "31pMZdRv"
    assert client.post(url, json={"answer": None}).json()["terminal"] is True
    assert client.post(url, json={"answer": "extra"}).status_code == 422


def test_routed_exit_page_survives_model_validation_and_preview():
    fixture = export("2130")
    step = fixture["content"]["steps"][3]
    step["exit_pages"] = [{"id": 956, "heading": "You cannot continue",
                           "markdown": "Contact the service team instead."}]
    step["routing_conditions"][0].update(goto_page_id=None, exit_page_id=956)
    definition = SFSMDefinition.model_validate(compile_form(fixture))
    states = definition.processes["main"].states
    output = states["mq4KgkUb__exit_1"]
    assert isinstance(output, OutputState)
    assert output.message == "You cannot continue\n\nContact the service team instead."
    assert isinstance(states[output.next], EndState)
    assert states[output.next].status == "offramp"
    run = PreviewRun(definition, definition.processes["main"].start)
    answer(run, "Z9qiMdb6", "I'm using this service as a member of the public")
    answer(run, "NeNd3HYi", "Satisfied")
    answer(run, "oygaerZY", "Feedback")
    result = answer(run, "mq4KgkUb", False)
    assert result["terminal"] and result["outcome"] == "exit_page"
    assert result["transcript"] == [output.message]


def test_optional_file_keeps_native_schema_and_can_be_skipped():
    fixture = export("6")
    question = fixture["content"]["steps"][1]
    question["data"].update(answer_type="file", is_optional=True)
    definition = SFSMDefinition.model_validate(compile_form(fixture))
    state = definition.processes["main"].states[question["id"]]
    assert state.schema_.kind == "file_ref" and state.schema_.allow_skip
    for value in (None, {"ref": "synthetic", "bytes": 123, "content_type": "application/pdf"}):
        run = PreviewRun(definition, definition.processes["main"].start)
        answer(run, "uyQrCFqM", "Alex Example")
        assert answer(run, question["id"], value)["answers"][question["id"]] == value


@pytest.mark.parametrize("changes,exits,error", [
    ({"answer_value": None, "goto_page_id": "nonexistent"}, [], "invalid routing target"),
    ({"answer_value": None, "goto_page_id": None, "exit_page_id": 98}, [], "unknown exit_page_id"),
    ({"answer_value": "No", "goto_page_id": None, "exit_page_id": 98},
     [{"id": 98, "heading": "", "markdown": ""}], "missing content"),
    ({"answer_value": "No", "goto_page_id": "31pMZdRv"},
     [{"id": 98, "heading": "Unused"}], "unreferenced exit_pages"),
])
def test_invalid_routing_fails_instead_of_falling_through(changes, exits, error):
    fixture = export("2130")
    step = fixture["content"]["steps"][3]
    step["exit_pages"] = exits
    step["routing_conditions"][0].update(changes)
    with pytest.raises(UnsupportedForm, match=error):
        compile_form(fixture)


def test_multiple_file_uploads_stay_unsupported():
    fixture = export("6")
    fixture["content"]["steps"][1]["data"].update(answer_type="file", answer_settings={"max_files": 3})
    with pytest.raises(UnsupportedForm, match="multiple file"):
        compile_form(fixture)


def test_payment_report_distinguishes_preview_only(tmp_path):
    fixture = export("6")
    fixture["content"]["payment_url"] = "https://payment.example.invalid/"
    src = tmp_path / "source.json"
    dst = tmp_path / "compiled.json"
    report = tmp_path / "report.json"
    src.write_text(json.dumps(fixture))
    process = subprocess.run([sys.executable, "-m", "forms_adapter", "--input", str(src),
                              "--output", str(dst), "--report", str(report)],
                             capture_output=True, text=True, cwd=FIXTURES.parents[2])
    assert process.returncode == 0, process.stderr
    assert json.loads(report.read_text())[0]["status"] == "preview_only"


def test_repeatable_question_compiles_to_native_sfsm_loop_and_validates():
    definition = compiled("repeatable")
    states = definition.processes["main"].states
    original = states["site"]
    assert original.assign == "repeat.site.current"
    assert original.next == "site__append"
    assert states["site__append"].set == {
        "answers.site": {"op": "append", "value_path": "repeat.site.current"}
    }
    assert states["site__append"].next == "site__more"
    assert states["site__more"].schema_.kind == "boolean"
    assert states["site__more"].schema_.model_extra["presentation"]["repeat_control"] is True
    assert states["site__repeat_route"].rules[0].when == {
        "op": "is_true", "path": "repeat.site.more"
    }
    assert states["site__repeat_route"].rules[0].next == "site"
    assert states["site__repeat_route"].default == "count"


@pytest.mark.parametrize("values", [
    ["1 Alpha Road, London"],
    ["1 Alpha Road, London", "2 Beta Road, Leeds"],
    ["1 Alpha Road, London", "2 Beta Road, Leeds", "3 Gamma Road, Cardiff"],
])
def test_repeatable_question_collects_every_answer_in_order(values):
    run = start("repeatable")
    first_token_like_visit = run.state_id
    assert first_token_like_visit == "site"
    for index, value in enumerate(values):
        result = answer(run, "site", value)
        assert result["interaction"]["id"] == "site__more"
        result = answer(run, "site__more", index < len(values) - 1)
        if index < len(values) - 1:
            assert result["interaction"]["id"] == "site"
        else:
            assert result["interaction"]["id"] == "count"
    assert run.answers["site"] == values
    assert answer(run, "count", "42")["terminal"]


def test_repeatable_invalid_answer_is_rejected_without_appending():
    run = start("repeatable")
    with pytest.raises(ValueError, match="Enter a value"):
        answer(run, "site", None)
    assert "site" not in run.answers
    assert run.state_id == "site"


def test_repeatable_selection_preserves_each_typed_answer():
    fixture = export("repeatable")
    q = fixture["content"]["steps"][0]
    q["data"]["answer_type"] = "selection"
    q["data"]["answer_settings"] = {
        "only_one_option": "true",
        "selection_options": [
            {"name": "London", "value": "london"},
            {"name": "Leeds", "value": "leeds"},
        ],
    }
    definition = SFSMDefinition.model_validate(compile_form(fixture))
    run = PreviewRun(definition, definition.processes[definition.entry].start)
    answer(run, "site", "london")
    answer(run, "site__more", True)
    answer(run, "site", "leeds")
    answer(run, "site__more", False)
    assert run.answers["site"] == ["london", "leeds"]


def test_optional_repeatable_is_rejected_conservatively():
    fixture = export("repeatable")
    fixture["content"]["steps"][0]["data"]["is_optional"] = True
    with pytest.raises(UnsupportedForm, match="optional repeatable"):
        compile_form(fixture)


def test_routing_on_or_from_repeatable_answer_is_rejected_conservatively():
    fixture = export("repeatable")
    fixture["content"]["steps"][0]["routing_conditions"] = [
        {"answer_value": "x", "goto_page_id": "count", "skip_to_end": False}
    ]
    with pytest.raises(UnsupportedForm, match="routing on a repeatable"):
        compile_form(fixture)

    fixture = export("repeatable")
    fixture["content"]["steps"][1]["routing_conditions"] = [
        {"check_page_id": "site", "routing_page_id": "count", "answer_value": "x", "skip_to_end": True}
    ]
    with pytest.raises(UnsupportedForm, match="depend on repeatable"):
        compile_form(fixture)
