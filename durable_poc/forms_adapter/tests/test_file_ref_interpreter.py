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
