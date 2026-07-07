from typing import Any

from jsonschema import FormatChecker
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for


class ArgumentsValidationError(ValueError):
    """Raised when submitted tool arguments do not satisfy the fixture schema."""

    def __init__(self, details: list[dict[str, Any]]) -> None:
        super().__init__("Tool arguments did not satisfy the fixture JSON Schema.")
        self.details = details


def function_definition(tool_schema: dict[str, Any]) -> dict[str, Any]:
    if tool_schema.get("type") != "function":
        raise ValueError("tool_schema.json must describe a function tool.")

    function = tool_schema.get("function")
    if not isinstance(function, dict):
        raise ValueError("tool_schema.json must contain a 'function' object.")
    return function


def tool_name(tool_schema: dict[str, Any]) -> str:
    name = function_definition(tool_schema).get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("The function tool must have a non-empty string name.")
    return name


def argument_schema(tool_schema: dict[str, Any]) -> dict[str, Any]:
    parameters = function_definition(tool_schema).get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("The function tool must contain a JSON Schema 'parameters' object.")

    validator_class = validator_for(parameters)
    try:
        validator_class.check_schema(parameters)
    except SchemaError as exc:
        raise ValueError(f"The tool parameters are not a valid JSON Schema: {exc.message}") from exc

    return parameters


def validate_arguments(schema: dict[str, Any], arguments: Any) -> dict[str, Any]:
    validator_class = validator_for(schema)
    validator = validator_class(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(arguments),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.message,
        ),
    )

    if errors:
        raise ArgumentsValidationError([validation_error_details(error) for error in errors])

    if not isinstance(arguments, dict):
        # Tool arguments are expected to be a JSON object. A fixture could technically
        # declare another root type, but LiteLLM function-tool arguments are object-shaped.
        raise ArgumentsValidationError(
            [
                {
                    "path": "$",
                    "schema_path": "$",
                    "validator": "type",
                    "message": "Tool arguments must be a JSON object.",
                }
            ]
        )

    return arguments


def validation_error_details(error: Any) -> dict[str, Any]:
    return {
        "path": json_path(error.absolute_path),
        "schema_path": json_path(error.absolute_schema_path),
        "validator": error.validator,
        "message": error.message,
    }


def json_path(parts: Any) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path
