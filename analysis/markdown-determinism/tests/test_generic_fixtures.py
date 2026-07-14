import json
from pathlib import Path

import pytest

from trivial_form_eval.analysis import analyse_run_dir, build_variants
from trivial_form_eval.evaluation import EvaluationContext, evaluate_response
from trivial_form_eval.fixture import load_fixture
from trivial_form_eval.request import build_request


def make_response(tool_name: str, arguments: object) -> dict:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {
        "id": "resp",
        "model": "returned",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call",
                            "type": "function",
                            "function": {"name": tool_name, "arguments": raw},
                        }
                    ],
                },
            }
        ],
    }


def classify(fixture_path: Path, tool_name: str, arguments: object) -> dict:
    fixture = load_fixture(fixture_path)
    return evaluate_response(
        run_number=1,
        requested_model="bedrock/test",
        start_time="2026-01-01T00:00:00+00:00",
        finish_time="2026-01-01T00:00:01+00:00",
        latency_seconds=1.0,
        attempts=1,
        response=make_response(tool_name, arguments),
        context=EvaluationContext.from_fixture(fixture),
    )


def write_registration_fixture(path: Path, include_evaluation: bool = False) -> None:
    path.mkdir()
    (path / "instructions.txt").write_text("Complete the registration.\n", encoding="utf-8")
    (path / "case.txt").write_text("Taylor attends with one guest.\n", encoding="utf-8")
    (path / "tool_schema.json").write_text(
        json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "submit_registration",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "reference": {"type": "string"},
                            "attendee": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string", "format": "email"},
                                },
                                "required": ["name", "email"],
                            },
                            "guest_names": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["reference", "attendee", "guest_names"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    expected = {
        "reference": "ABC-123",
        "attendee": {"name": "Taylor Singh", "email": "taylor@example.com"},
        "guest_names": ["Morgan Lee"],
    }
    (path / "expected_arguments.json").write_text(json.dumps(expected), encoding="utf-8")
    if include_evaluation:
        (path / "evaluation.json").write_text(
            json.dumps({"accepted_equivalence_rules": []}), encoding="utf-8"
        )


def test_tool_name_and_schema_come_from_fixture(tmp_path: Path) -> None:
    fixture_path = tmp_path / "registration"
    write_registration_fixture(fixture_path)
    fixture = load_fixture(fixture_path)

    assert fixture.expected_tool_name == "submit_registration"
    assert build_request(fixture, "bedrock/test").tool_choice == {
        "type": "function",
        "function": {"name": "submit_registration"},
    }

    correct = classify(fixture_path, "submit_registration", fixture.expected_arguments)
    wrong_tool = classify(fixture_path, "submit_contact_details", fixture.expected_arguments)
    missing_nested = classify(
        fixture_path,
        "submit_registration",
        {
            "reference": "ABC-123",
            "attendee": {"name": "Taylor Singh"},
            "guest_names": ["Morgan Lee"],
        },
    )
    extra_field = classify(
        fixture_path,
        "submit_registration",
        {**fixture.expected_arguments, "unexpected": True},
    )

    assert correct["status"] == "correct"
    assert wrong_tool["status"] == "wrong_tool"
    assert missing_nested["status"] == "schema_invalid_arguments"
    assert missing_nested["errors"][0]["details"][0]["path"] == "$.attendee"
    assert extra_field["status"] == "schema_invalid_arguments"


def test_new_fixture_defaults_to_exact_semantic_equality(tmp_path: Path) -> None:
    fixture_path = tmp_path / "registration"
    write_registration_fixture(fixture_path)
    fixture = load_fixture(fixture_path)
    changed = json.loads(json.dumps(fixture.expected_arguments))
    changed["guest_names"] = ["Morgan L."]

    result = classify(fixture_path, "submit_registration", changed)

    assert fixture.evaluation_config == {"accepted_equivalence_rules": []}
    assert result["status"] == "incorrect_arguments"
    assert not result["accepted_match_to_expected"]


def test_contact_equivalence_is_fixture_scoped() -> None:
    fixture_path = Path("fixtures/trivial_contact")
    fixture = load_fixture(fixture_path)
    combined = json.loads(json.dumps(fixture.expected_arguments))
    combined["address"]["address_line_1"] = "Flat 4B, 18 Orchard Lane"
    combined["address"]["address_line_2"] = ""

    result = classify(fixture_path, "submit_contact_details", combined)

    assert result["status"] == "correct"
    assert not result["exact_match_to_expected"]
    assert result["accepted_match_to_expected"]


def test_invalid_expected_arguments_fail_when_fixture_loads(tmp_path: Path) -> None:
    fixture_path = tmp_path / "registration"
    write_registration_fixture(fixture_path)
    (fixture_path / "expected_arguments.json").write_text(
        json.dumps({"reference": "ABC-123"}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="does not satisfy"):
        load_fixture(fixture_path)


def test_saved_evaluation_policy_is_reapplied(tmp_path: Path) -> None:
    fixture_path = Path("fixtures/trivial_contact")
    fixture = load_fixture(fixture_path)
    combined = json.loads(json.dumps(fixture.expected_arguments))
    combined["address"]["address_line_1"] = "Flat 4B, 18 Orchard Lane"
    combined["address"]["address_line_2"] = ""
    record = classify(fixture_path, "submit_contact_details", combined)
    record["status"] = "incorrect_arguments"
    record["accepted_match_to_expected"] = False

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "expected_arguments.json").write_text(
        json.dumps(fixture.expected_arguments), encoding="utf-8"
    )
    (run_dir / "evaluation.json").write_text(
        json.dumps(fixture.evaluation_config), encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(json.dumps({"requested_runs": 1}), encoding="utf-8")
    (run_dir / "responses.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    summary, variants, _ = analyse_run_dir(run_dir)

    assert summary["correct_count"] == 1
    assert variants["variants"][0]["accepted_match_to_expected"]


def test_build_variants_can_reuse_record_policy_for_old_callers() -> None:
    fixture_path = Path("fixtures/trivial_contact")
    fixture = load_fixture(fixture_path)
    combined = json.loads(json.dumps(fixture.expected_arguments))
    combined["address"]["address_line_1"] = "Flat 4B, 18 Orchard Lane"
    combined["address"]["address_line_2"] = ""
    record = classify(fixture_path, "submit_contact_details", combined)

    variants = build_variants([record], fixture.expected_arguments)

    assert variants["variants"][0]["accepted_match_to_expected"]
