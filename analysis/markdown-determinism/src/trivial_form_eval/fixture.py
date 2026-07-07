import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trivial_form_eval.comparison import normalise_evaluation_config
from trivial_form_eval.schema import (
    ArgumentsValidationError,
    argument_schema,
    tool_name,
    validate_arguments,
)


@dataclass(frozen=True)
class Fixture:
    path: Path
    instructions_text: str
    case_text: str
    tool_schema: dict[str, Any]
    expected_arguments: dict[str, Any]
    expected_tool_name: str
    arguments_schema: dict[str, Any]
    evaluation_config: dict[str, Any]


def load_fixture(path: Path) -> Fixture:
    path = path.resolve()
    tool_schema = load_json_object(path / "tool_schema.json")
    expected_arguments = load_json_object(path / "expected_arguments.json")
    expected_tool_name = tool_name(tool_schema)
    arguments_schema = argument_schema(tool_schema)
    evaluation_config = load_optional_evaluation_config(path / "evaluation.json")

    try:
        validate_arguments(arguments_schema, expected_arguments)
    except ArgumentsValidationError as exc:
        raise ValueError(
            "expected_arguments.json does not satisfy the fixture tool schema: "
            + json.dumps(exc.details, ensure_ascii=False)
        ) from exc

    return Fixture(
        path=path,
        instructions_text=(path / "instructions.txt").read_text(encoding="utf-8"),
        case_text=(path / "case.txt").read_text(encoding="utf-8"),
        tool_schema=tool_schema,
        expected_arguments=expected_arguments,
        expected_tool_name=expected_tool_name,
        arguments_schema=arguments_schema,
        evaluation_config=evaluation_config,
    )


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return value


def load_optional_evaluation_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return normalise_evaluation_config(None)
    return normalise_evaluation_config(json.loads(path.read_text(encoding="utf-8")))
