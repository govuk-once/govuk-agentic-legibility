"""Tests for bounded interaction assistance and schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agents.src.interaction_assistant import (
    AssistanceAction,
    InteractionAssistantError,
    validate_assistance_action,
)


def address_interaction() -> dict[str, object]:
    """Return an interaction containing required and nullable scalar fields."""
    return {
        "id": "enter_address_manually",
        "input_schema": {
            "type": "object",
            "properties": {
                "address_line_1": {"type": "string"},
                "address_line_2": {"type": ["string", "null"]},
                "postcode": {"type": ["string", "null"]},
                "use_postcode_lookup": {"type": "boolean"},
            },
        },
    }


def test_partial_proposal_is_validated_against_current_schema() -> None:
    """The assistant may propose a safe subset of the current interaction fields."""
    action = AssistanceAction(
        type="propose_values",
        values={"address_line_1": "18 Station Road", "postcode": "BS1 3AB"},
    )

    assert validate_assistance_action(action, address_interaction()) is action


def test_nullable_schema_field_accepts_null() -> None:
    """JSON Schema nullable scalar fields remain valid assistant outputs."""
    action = AssistanceAction(
        type="propose_values",
        values={"address_line_2": None},
    )

    assert validate_assistance_action(action, address_interaction()) is action


def test_proposal_rejects_fields_outside_current_schema() -> None:
    """An assistant cannot introduce a field the current interaction did not expose."""
    action = AssistanceAction(
        type="propose_values",
        values={"next_action": "/complete"},
    )

    with pytest.raises(InteractionAssistantError, match="outside the current schema"):
        validate_assistance_action(action, address_interaction())


def test_proposal_rejects_value_with_wrong_schema_type() -> None:
    """Proposed values must have the scalar type advertised by the service."""
    action = AssistanceAction(
        type="propose_values",
        values={"use_postcode_lookup": "yes"},
    )

    with pytest.raises(InteractionAssistantError, match="does not match"):
        validate_assistance_action(action, address_interaction())


def test_no_safe_suggestion_requires_message_and_no_values() -> None:
    """The no-suggestion action cannot silently carry proposed form values."""
    with pytest.raises(ValidationError):
        AssistanceAction(type="no_safe_suggestion")

    with pytest.raises(ValidationError):
        AssistanceAction(
            type="no_safe_suggestion",
            values={"postcode": "BS1 3AB"},
            message="Complete the form manually.",
        )
