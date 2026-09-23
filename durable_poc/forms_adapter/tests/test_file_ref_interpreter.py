"""Real interpreter validation, if temporalio is installed."""

import pytest

pytest.importorskip("temporalio")

from src.context import AwaitingInput, InputSubmission
from src.errors import InputValidationError
from src.interpreter import SFSMInterpreter


def test_optional_file_ref_can_be_skipped_but_required_cannot(monkeypatch):
    interpreter = SFSMInterpreter()
    interpreter._awaiting_input = AwaitingInput(
        token="tkn_1", prompt="Attach synthetic document",
        schema={"kind": "file_ref", "allow_skip": True},
    )
    interpreter._validate_input(InputSubmission(token="tkn_1", value=None))
    interpreter._validate_input(InputSubmission(token="tkn_1", value={
        "ref": "synthetic", "bytes": 12, "content_type": "application/pdf"}))
    interpreter._awaiting_input.schema["allow_skip"] = False

    def reject(*args, **kwargs):
        raise InputValidationError(kwargs["message"])

    monkeypatch.setattr(interpreter, "_raise_input_validation_error", reject)
    with pytest.raises(InputValidationError, match="Invalid file upload"):
        interpreter._validate_input(InputSubmission(token="tkn_1", value=None))


def test_exclusive_none_of_the_above_rejected_by_temporal_validator(monkeypatch):
    # No Temporal server: exercise the existing update validator directly.
    interpreter = SFSMInterpreter()
    interpreter._awaiting_input = AwaitingInput(
        token="tkn_none", prompt="Which terms?",
        schema={
            "kind": "select_many",
            "options": [
                {"value": "resignation", "label": "Resignation"},
                {"value": "none_of_the_above", "label": "None of the above"},
            ],
            "exclusive_options": ["none_of_the_above"],
        },
    )

    def reject(*args, **kwargs):
        raise InputValidationError(kwargs["message"])

    monkeypatch.setattr(interpreter, "_raise_input_validation_error", reject)
    interpreter._validate_input(InputSubmission(token="tkn_none", value=["none_of_the_above"]))
    interpreter._validate_input(InputSubmission(token="tkn_none", value=["resignation"]))
    with pytest.raises(InputValidationError, match="cannot be combined"):
        interpreter._validate_input(InputSubmission(
            token="tkn_none", value=["resignation", "none_of_the_above"]
        ))
