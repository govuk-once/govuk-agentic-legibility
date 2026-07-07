import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from trivial_form_eval.comparison import (
    LEGACY_CONTACT_EVALUATION_CONFIG,
    accepted_match,
)
from trivial_form_eval.diffing import field_differences, unified_json_diff
from trivial_form_eval.fixture import Fixture
from trivial_form_eval.jsonutil import canonical_json, pretty_json
from trivial_form_eval.normalize import (
    finish_reason,
    first_choice,
    get_value,
    infer_provider,
    message_from_choice,
    response_cost,
    response_usage,
    serialise_safe,
)
from trivial_form_eval.schema import ArgumentsValidationError, validate_arguments

TRANSIENT_EXCEPTION_NAMES = (
    "RateLimitError",
    "APIConnectionError",
    "APIConnectionTimeoutError",
    "Timeout",
    "ServiceUnavailableError",
    "InternalServerError",
    "ThrottlingException",
    "ModelTimeoutException",
)


@dataclass(frozen=True)
class EvaluationContext:
    expected_arguments: dict[str, Any]
    expected_canonical: str
    expected_tool_name: str
    arguments_schema: dict[str, Any]
    evaluation_config: dict[str, Any]

    @classmethod
    def from_fixture(cls, fixture: Fixture) -> "EvaluationContext":
        return cls(
            expected_arguments=fixture.expected_arguments,
            expected_canonical=canonical_json(fixture.expected_arguments),
            expected_tool_name=fixture.expected_tool_name,
            arguments_schema=fixture.arguments_schema,
            evaluation_config=fixture.evaluation_config,
        )

    @classmethod
    def from_expected(cls, expected_arguments: dict[str, Any]) -> "EvaluationContext":
        """Build the old contact-fixture context for backwards-compatible tests.

        New code should always use ``from_fixture`` so the tool name, schema and
        comparison policy come from the selected fixture.
        """
        return cls(
            expected_arguments=expected_arguments,
            expected_canonical=canonical_json(expected_arguments),
            expected_tool_name="submit_contact_details",
            arguments_schema=_schema_from_example(expected_arguments),
            evaluation_config=LEGACY_CONTACT_EVALUATION_CONFIG,
        )


def _schema_from_example(value: Any) -> dict[str, Any]:
    """Infer a strict schema for the deprecated ``from_expected`` helper."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {key: _schema_from_example(item) for key, item in value.items()},
            "required": list(value),
            "additionalProperties": False,
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "items": _schema_from_example(value[0]) if value else {},
        }
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if value is None:
        return {"type": "null"}
    return {}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def is_transient_exception(exc: Exception) -> bool:
    return exc.__class__.__name__ in TRANSIENT_EXCEPTION_NAMES


def evaluate_response(
    *,
    run_number: int,
    requested_model: str,
    start_time: str,
    finish_time: str,
    latency_seconds: float,
    attempts: int,
    response: Any,
    context: EvaluationContext,
) -> dict[str, Any]:
    choice = first_choice(response)
    message = message_from_choice(choice)
    tool_calls = get_value(message, "tool_calls", []) or []
    content = get_value(message, "content")
    tool_call_ids = [get_value(call, "id") for call in tool_calls]
    tool_names = [get_value(get_value(call, "function", {}), "name") for call in tool_calls]
    raw_arguments = [get_value(get_value(call, "function", {}), "arguments") for call in tool_calls]

    result = base_run_record(
        run_number=run_number,
        status="unexpected_response",
        start_time=start_time,
        finish_time=finish_time,
        latency_seconds=latency_seconds,
        attempts=attempts,
        requested_model=requested_model,
        response=response,
        finish_reason=finish_reason(choice),
        content=content,
        tool_calls=tool_calls,
        tool_call_ids=tool_call_ids,
        tool_names=tool_names,
        raw_arguments=raw_arguments,
    )

    if not tool_calls:
        result["status"] = "refusal_or_prose_only" if content else "no_tool_call"
        result["errors"].append(
            {"kind": result["status"], "message": "Response contained no tool calls."}
        )
        return result

    if len(tool_calls) > 1:
        result["status"] = "multiple_tool_calls"
        result["errors"].append({"kind": "multiple_tool_calls", "count": len(tool_calls)})
        return result

    if tool_names != [context.expected_tool_name]:
        result["status"] = "wrong_tool"
        result["errors"].append(
            {
                "kind": "wrong_tool",
                "expected_tool_name": context.expected_tool_name,
                "called_tool_names": tool_names,
            }
        )
        return result

    result["exactly_one_correct_tool_call"] = True
    raw = raw_arguments[0]

    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        result["status"] = "malformed_arguments"
        result["errors"].append(
            {
                "kind": "malformed_arguments",
                "message": exc.msg,
                "line": exc.lineno,
                "column": exc.colno,
            }
        )
        return result

    result["arguments_parseable"] = True
    result["parsed_tool_arguments"] = parsed
    result["pretty_parsed_arguments"] = pretty_json(parsed)

    try:
        validated = validate_arguments(context.arguments_schema, parsed)
    except ArgumentsValidationError as exc:
        result["status"] = "schema_invalid_arguments"
        result["errors"].append({"kind": "schema_invalid_arguments", "details": exc.details})
        return result

    result["schema_valid"] = True
    result["parsed_tool_arguments"] = validated
    result["pretty_parsed_arguments"] = pretty_json(validated)
    result["canonical_tool_arguments"] = canonical_json(validated)
    result["exact_match_to_expected"] = (
        result["canonical_tool_arguments"] == context.expected_canonical
    )
    result["accepted_match_to_expected"] = accepted_match(
        context.expected_arguments,
        validated,
        context.evaluation_config,
    )

    if result["accepted_match_to_expected"]:
        result["status"] = "correct"
    else:
        result["status"] = "incorrect_arguments"
        result["field_differences"] = field_differences(context.expected_arguments, validated)
        result["unified_diff"] = unified_json_diff(context.expected_arguments, validated)

    return result


def evaluate_api_failure(
    *,
    run_number: int,
    requested_model: str,
    start_time: str,
    finish_time: str,
    latency_seconds: float,
    attempts: int,
    exc: Exception,
) -> dict[str, Any]:
    transient = is_transient_exception(exc)
    return {
        "run_number": run_number,
        "status": "transient_api_failure_exhausted" if transient else "non_transient_api_failure",
        "start_time": start_time,
        "finish_time": finish_time,
        "latency_seconds": latency_seconds,
        "api_attempts": attempts,
        "litellm_response_id": None,
        "requested_model": requested_model,
        "returned_model": None,
        "provider": None,
        "finish_reason": None,
        "assistant_content": None,
        "tool_call_count": 0,
        "tool_call_ids": [],
        "called_tool_names": [],
        "raw_tool_argument_strings": [],
        "parsed_tool_arguments": None,
        "pretty_parsed_arguments": None,
        "canonical_tool_arguments": None,
        "exactly_one_correct_tool_call": False,
        "arguments_parseable": False,
        "schema_valid": False,
        "exact_match_to_expected": False,
        "accepted_match_to_expected": False,
        "errors": [
            {
                "kind": "api_failure",
                "exception_type": exc.__class__.__name__,
                "message": str(exc),
                "transient": transient,
            }
        ],
        "token_usage": None,
        "estimated_cost": None,
        "raw_response": None,
    }


def base_run_record(
    *,
    run_number: int,
    status: str,
    start_time: str,
    finish_time: str,
    latency_seconds: float,
    attempts: int,
    requested_model: str,
    response: Any,
    finish_reason: Any,
    content: Any,
    tool_calls: list[Any],
    tool_call_ids: list[Any],
    tool_names: list[Any],
    raw_arguments: list[Any],
) -> dict[str, Any]:
    return {
        "run_number": run_number,
        "status": status,
        "start_time": start_time,
        "finish_time": finish_time,
        "latency_seconds": latency_seconds,
        "api_attempts": attempts,
        "litellm_response_id": get_value(response, "id"),
        "requested_model": requested_model,
        "returned_model": get_value(response, "model"),
        "provider": infer_provider(response, requested_model),
        "finish_reason": finish_reason,
        "assistant_content": content,
        "tool_call_count": len(tool_calls),
        "tool_call_ids": tool_call_ids,
        "called_tool_names": tool_names,
        "raw_tool_argument_strings": raw_arguments,
        "parsed_tool_arguments": None,
        "pretty_parsed_arguments": None,
        "canonical_tool_arguments": None,
        "exactly_one_correct_tool_call": False,
        "arguments_parseable": False,
        "schema_valid": False,
        "exact_match_to_expected": False,
        "accepted_match_to_expected": False,
        "errors": [],
        "token_usage": response_usage(response),
        "estimated_cost": response_cost(response),
        "raw_response": serialise_safe(response),
    }
