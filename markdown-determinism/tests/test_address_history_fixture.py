import json
from pathlib import Path

from trivial_form_eval.evaluation import EvaluationContext, evaluate_response
from trivial_form_eval.fixture import load_fixture
from trivial_form_eval.request import build_request

FIXTURE_PATH = Path("fixtures/address_history")


def make_response(tool_name: str, arguments: object) -> dict:
    raw_arguments = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {
        "id": "response-id",
        "model": "returned-model",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tool-call-id",
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": raw_arguments,
                            },
                        }
                    ],
                },
            }
        ],
    }


def classify(arguments: object) -> dict:
    fixture = load_fixture(FIXTURE_PATH)
    return evaluate_response(
        run_number=1,
        requested_model="bedrock/test",
        start_time="2026-01-01T00:00:00+00:00",
        finish_time="2026-01-01T00:00:01+00:00",
        latency_seconds=1.0,
        attempts=1,
        response=make_response(fixture.expected_tool_name, arguments),
        context=EvaluationContext.from_fixture(fixture),
    )


def test_address_history_fixture_loads_and_builds_request() -> None:
    fixture = load_fixture(FIXTURE_PATH)
    request = build_request(fixture, "bedrock/test")

    assert fixture.expected_tool_name == "submit_address_history"
    assert len(fixture.expected_arguments["previous_addresses"]) == 2
    assert request.tool_choice == {
        "type": "function",
        "function": {"name": "submit_address_history"},
    }


def test_expected_address_history_is_correct() -> None:
    fixture = load_fixture(FIXTURE_PATH)

    result = classify(fixture.expected_arguments)

    assert result["status"] == "correct"
    assert result["schema_valid"]
    assert result["exact_match_to_expected"]
    assert result["accepted_match_to_expected"]


def test_previous_address_order_is_semantically_significant() -> None:
    fixture = load_fixture(FIXTURE_PATH)
    reversed_history = json.loads(json.dumps(fixture.expected_arguments))
    reversed_history["previous_addresses"].reverse()

    result = classify(reversed_history)

    assert result["status"] == "incorrect_arguments"
    assert result["schema_valid"]
    assert not result["exact_match_to_expected"]
    assert not result["accepted_match_to_expected"]
