import json
from pathlib import Path

import pytest

import trivial_form_eval.runner as runner
from trivial_form_eval.analysis import analyse_run_dir, build_summary, build_variants
from trivial_form_eval.diffing import field_differences, unified_json_diff
from trivial_form_eval.evaluation import EvaluationContext, evaluate_response
from trivial_form_eval.fixture import load_fixture
from trivial_form_eval.jsonutil import canonical_json
from trivial_form_eval.request import EXPECTED_TOOL_NAME, build_request, resolve_model
from trivial_form_eval.runner import execute_one, run_experiment

FIXTURE = Path("fixtures/trivial_contact")


def expected_args() -> dict:
    return load_fixture(FIXTURE).expected_arguments


def raw_args(value: dict | None = None, **updates: object) -> str:
    data = expected_args() if value is None else value
    data = json.loads(json.dumps(data))
    data.update(updates)
    return json.dumps(data)


def with_address_lines(line_1: str, line_2: str) -> dict:
    data = expected_args()
    data["address"] = {
        **data["address"],
        "address_line_1": line_1,
        "address_line_2": line_2,
    }
    return data


def response(
    *,
    raw: str | None = None,
    tool_name: str = EXPECTED_TOOL_NAME,
    tool_calls: list[dict] | None = None,
    content: str | None = None,
) -> dict:
    if tool_calls is None and raw is not None:
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": tool_name, "arguments": raw},
            }
        ]
    return {
        "id": "resp_1",
        "model": "returned-model",
        "_hidden_params": {"custom_llm_provider": "openai", "response_cost": 0.001},
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "choices": [
            {
                "finish_reason": "tool_calls" if tool_calls else "stop",
                "message": {"content": content, "tool_calls": tool_calls or []},
            }
        ],
    }


def classify(resp: dict) -> dict:
    return evaluate_response(
        run_number=1,
        requested_model="bedrock/test",
        start_time="2026-01-01T00:00:00+00:00",
        finish_time="2026-01-01T00:00:01+00:00",
        latency_seconds=1.0,
        attempts=1,
        response=resp,
        context=EvaluationContext.from_expected(expected_args()),
    )


def test_deterministic_request_construction_and_tool_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_fixture(FIXTURE)
    monkeypatch.setenv("LITELLM_MODEL", "bedrock/env-model")
    request_a = build_request(fixture, resolve_model(None)).as_saved_json()
    request_b = build_request(fixture, resolve_model(None)).as_saved_json()

    assert request_a == request_b
    assert request_a["model"] == "bedrock/env-model"
    assert request_a["tools"] == [fixture.tool_schema]
    assert request_a["tool_choice"] == {
        "type": "function",
        "function": {"name": EXPECTED_TOOL_NAME},
    }
    assert "expected_arguments" not in request_a
    assert all("expected_arguments" not in message["content"] for message in request_a["messages"])


def test_cli_model_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MODEL", "bedrock/env-model")
    assert resolve_model("bedrock/cli-model") == "bedrock/cli-model"


def test_canonical_and_raw_comparison_behaviour() -> None:
    left = '{"a": 1, "b": 2}'
    different_whitespace = '{"a":1,"b":2}'
    different_order = '{"b":2,"a":1}'

    assert left != different_whitespace
    assert left != different_order
    assert canonical_json(json.loads(left)) == canonical_json(json.loads(different_whitespace))
    assert canonical_json(json.loads(left)) == canonical_json(json.loads(different_order))


@pytest.mark.parametrize(
    ("resp", "status"),
    [
        (response(raw=raw_args()), "correct"),
        (response(tool_calls=[]), "no_tool_call"),
        (response(tool_calls=[], content="I cannot do that."), "refusal_or_prose_only"),
        (response(raw=raw_args(), tool_name="wrong_tool"), "wrong_tool"),
        (
            response(
                tool_calls=[
                    {"id": "1", "function": {"name": EXPECTED_TOOL_NAME, "arguments": raw_args()}},
                    {"id": "2", "function": {"name": EXPECTED_TOOL_NAME, "arguments": raw_args()}},
                ]
            ),
            "multiple_tool_calls",
        ),
        (response(raw="{not json"), "malformed_arguments"),
        (response(raw=raw_args({"full_name": "Alex Morgan"})), "schema_invalid_arguments"),
        (response(raw=raw_args(full_name="Alexa Morgan")), "incorrect_arguments"),
    ],
)
def test_response_classification(resp: dict, status: str) -> None:
    result = classify(resp)
    assert result["status"] == status


def test_correct_arguments_accept_different_key_order_and_whitespace() -> None:
    raw = json.dumps(expected_args(), indent=4, sort_keys=True)
    result = classify(response(raw=raw))

    assert result["status"] == "correct"
    assert result["exact_match_to_expected"]
    assert result["raw_tool_argument_strings"] == [raw]


def test_combined_address_lines_are_accepted_but_not_exact() -> None:
    result = classify(response(raw=raw_args(with_address_lines("Flat 4B, 18 Orchard Lane", ""))))

    assert result["status"] == "correct"
    assert not result["exact_match_to_expected"]
    assert result["accepted_match_to_expected"]


def test_address_lines_may_be_reordered_without_being_punished() -> None:
    result = classify(response(raw=raw_args(with_address_lines("Flat 4B", "18 Orchard Lane"))))

    assert result["status"] == "correct"
    assert not result["exact_match_to_expected"]
    assert result["accepted_match_to_expected"]


def test_address_lines_with_extra_words_are_incorrect() -> None:
    result = classify(
        response(raw=raw_args(with_address_lines("Flat 4B, 18 Orchard Lane, Bristol", "")))
    )

    assert result["status"] == "incorrect_arguments"
    assert not result["accepted_match_to_expected"]


def test_nested_field_mismatch_and_diff_generation() -> None:
    actual = expected_args()
    actual["address"] = {**actual["address"], "address_line_1": "Flat 4B"}
    actual["research_contact_consent"] = True

    fields = field_differences(expected_args(), actual)
    paths = {item["path"] for item in fields}
    diff = unified_json_diff(expected_args(), actual)

    assert "address.address_line_1" in paths
    assert "research_contact_consent" in paths
    assert "--- expected" in diff
    assert "+++ actual" in diff
    assert '"research_contact_consent": true' in diff


def test_summary_and_variants_for_repeated_and_distinct_outputs() -> None:
    correct_a = classify(response(raw=raw_args()))
    correct_b = classify(response(raw=json.dumps(expected_args(), indent=2, sort_keys=True)))
    accepted_non_exact = classify(
        response(raw=raw_args(with_address_lines("Flat 4B, 18 Orchard Lane", "")))
    )
    incorrect = classify(response(raw=raw_args(full_name="Alexa Morgan")))
    malformed = classify(response(raw="{bad"))
    records = [correct_a, correct_b, accepted_non_exact, incorrect, malformed]

    summary = build_summary(records, expected_args(), requested_runs=5)
    variants = build_variants(records, expected_args())

    assert summary["correct_count"] == 3
    assert summary["completion_rate"] == 1
    assert summary["correct_rate"] == 0.6
    assert summary["exact_expected_match_count"] == 2
    assert summary["exact_expected_match_rate"] == 0.4
    assert summary["accepted_expected_match_count"] == 3
    assert summary["accepted_expected_match_rate"] == 0.6
    assert summary["semantically_incorrect_count"] == 1
    assert summary["malformed_arguments_count"] == 1
    assert summary["unique_raw_tool_argument_strings"] == 5
    assert summary["unique_canonical_valid_argument_objects"] == 3
    assert not summary["all_successful_raw_tool_argument_strings_identical"]
    assert not summary["all_schema_valid_parsed_outputs_semantically_identical"]
    assert [variant["variant_id"] for variant in variants["variants"]] == [
        "variant_001",
        "variant_002",
        "variant_003",
    ]
    assert sum(1 for variant in variants["variants"] if variant["accepted_match_to_expected"]) == 2
    assert variants["non_valid_outcome_categories"]["malformed_arguments"]["count"] == 1


class RateLimitError(Exception):
    pass


def test_transient_litellm_exceptions_are_retried() -> None:
    calls = 0

    def completion(**_kwargs: object) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimitError("slow down")
        return response(raw=raw_args())

    record = execute_one(
        run_number=1,
        request_snapshot={"model": "bedrock/test"},
        requested_model="bedrock/test",
        max_retries=1,
        completion_func=completion,
        context=EvaluationContext.from_expected(expected_args()),
    )

    assert calls == 2
    assert record["status"] == "correct"
    assert record["api_attempts"] == 2


def test_transient_exhaustion_and_non_transient_failure() -> None:
    def transient(**_kwargs: object) -> dict:
        raise RateLimitError("still failing")

    def non_transient(**_kwargs: object) -> dict:
        raise ValueError("bad request")

    transient_record = execute_one(
        run_number=1,
        request_snapshot={},
        requested_model="bedrock/test",
        max_retries=1,
        completion_func=transient,
        context=EvaluationContext.from_expected(expected_args()),
    )
    non_transient_record = execute_one(
        run_number=1,
        request_snapshot={},
        requested_model="bedrock/test",
        max_retries=3,
        completion_func=non_transient,
        context=EvaluationContext.from_expected(expected_args()),
    )

    assert transient_record["status"] == "transient_api_failure_exhausted"
    assert transient_record["api_attempts"] == 2
    assert non_transient_record["status"] == "non_transient_api_failure"
    assert non_transient_record["api_attempts"] == 1


def test_runner_loads_fixture_once_and_keeps_request_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = load_fixture(FIXTURE)
    load_count = 0
    seen_requests = []

    def fake_load_fixture(path: Path):
        nonlocal load_count
        load_count += 1
        assert path == FIXTURE
        return fixture

    def completion(**kwargs: object) -> dict:
        seen_requests.append(json.loads(json.dumps(kwargs)))
        return response(raw=raw_args())

    monkeypatch.setattr(runner, "load_fixture", fake_load_fixture)
    monkeypatch.setattr(runner, "run_id", lambda: "fixed-run")

    run_dir = run_experiment(
        fixture_path=FIXTURE,
        runs=2,
        model="bedrock/test",
        concurrency=1,
        output_dir=tmp_path,
        max_retries=0,
        completion_func=completion,
    )

    assert load_count == 1
    assert seen_requests[0] == seen_requests[1]
    assert run_dir == tmp_path / "fixed-run"
    assert (run_dir / "request.json").exists()
    assert (run_dir / "expected_arguments.json").exists()
    assert len((run_dir / "responses.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))[
        "every_requested_run_correct"
    ]


def test_runner_stop_after_writes_partial_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "run_id", lambda: "partial-run")

    run_dir = run_experiment(
        fixture_path=FIXTURE,
        runs=5,
        model="bedrock/test",
        concurrency=1,
        output_dir=tmp_path,
        max_retries=0,
        completion_func=lambda **_kwargs: response(raw=raw_args()),
        stop_after=2,
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert len((run_dir / "responses.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert manifest["stop_reason"] == "stop_after"
    assert manifest["completed_runs"] == 2
    assert summary["requested_runs"] == 5
    assert summary["completed_runs"] == 2
    assert summary["completion_rate"] == 0.4
    assert summary["correct_rate"] == 1
    assert summary["schema_valid_rate"] == 1
    assert not summary["all_requested_runs_completed"]


def test_runner_keyboard_interrupt_finalises_partial_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "run_id", lambda: "interrupted-run")
    calls = 0

    def completion(**_kwargs: object) -> dict:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise KeyboardInterrupt
        return response(raw=raw_args())

    run_dir = run_experiment(
        fixture_path=FIXTURE,
        runs=5,
        model="bedrock/test",
        concurrency=1,
        output_dir=tmp_path,
        max_retries=0,
        completion_func=completion,
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert calls == 3
    assert len((run_dir / "responses.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert manifest["stop_reason"] == "keyboard_interrupt"
    assert manifest["completed_runs"] == 2
    assert summary["completed_runs"] == 2
    assert (run_dir / "variants.json").exists()
    assert (run_dir / "differences.txt").exists()


def test_analysis_of_existing_completed_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "saved"
    run_dir.mkdir()
    (run_dir / "expected_arguments.json").write_text(json.dumps(expected_args()), encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"requested_runs": 1}), encoding="utf-8")
    record = classify(response(raw=raw_args(full_name="Alexa Morgan")))
    (run_dir / "responses.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    summary, variants, differences = analyse_run_dir(run_dir)

    assert summary["completed_runs"] == 1
    assert summary["semantically_incorrect_count"] == 1
    assert variants["variants"][0]["variant_id"] == "variant_001"
    assert "Alexa Morgan" in differences


def test_analysis_reapplies_current_address_line_policy_to_saved_runs(tmp_path: Path) -> None:
    run_dir = tmp_path / "saved"
    run_dir.mkdir()
    (run_dir / "expected_arguments.json").write_text(json.dumps(expected_args()), encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"requested_runs": 1}), encoding="utf-8")
    record = classify(response(raw=raw_args(with_address_lines("Flat 4B, 18 Orchard Lane", ""))))
    record["status"] = "incorrect_arguments"
    record["accepted_match_to_expected"] = False
    (run_dir / "responses.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    summary, variants, differences = analyse_run_dir(run_dir)

    assert summary["correct_count"] == 1
    assert summary["exact_expected_match_count"] == 0
    assert summary["accepted_expected_match_count"] == 1
    assert summary["semantically_incorrect_count"] == 0
    assert variants["variants"][0]["accepted_match_to_expected"]
    assert "Accepted non-exact semantic variants" in differences
