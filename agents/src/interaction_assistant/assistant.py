"""Framework-neutral interface and output validation for interaction assistance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, Protocol, Self, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agents.src.workflow_executor.types import JsonObject, ReadOnlyJsonObject

JsonScalar: TypeAlias = str | int | float | bool | None


class InteractionAssistantError(RuntimeError):
    """Raised when interaction assistance cannot be produced or validated."""


class ConversationMessage(BaseModel):
    """One user-visible message supplied as context to the assistant."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class AssistanceRequest(BaseModel):
    """Complete conversation and current interaction available to the assistant."""

    model_config = ConfigDict(extra="forbid")

    conversation: list[ConversationMessage] = Field(min_length=1)
    interaction: JsonObject


class AssistanceAction(BaseModel):
    """A bounded action returned by the interaction assistant."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["propose_values", "no_safe_suggestion"] = Field(
        description="The single bounded action selected for the current interaction"
    )
    values: dict[str, JsonScalar] = Field(
        default_factory=dict,
        description="Current-schema field names and safely supported scalar values",
    )
    message: str | None = Field(
        default=None,
        description="Short user-facing explanation for no_safe_suggestion",
    )

    @model_validator(mode="after")
    def validate_action_shape(self) -> Self:
        """Require values only for proposals and a message for no suggestion."""
        if self.type == "propose_values" and not self.values:
            msg = "propose_values must contain at least one value"
            raise ValueError(msg)
        if self.type == "no_safe_suggestion" and self.values:
            msg = "no_safe_suggestion must not contain proposed values"
            raise ValueError(msg)
        if self.type == "no_safe_suggestion" and not self.message:
            msg = "no_safe_suggestion must include a message"
            raise ValueError(msg)
        return self


class InteractionAssistant(Protocol):
    """Produce a bounded action for the current interaction only."""

    @property
    def model_id(self) -> str:
        """Return the configured model identifier."""

    @property
    def prompt_id(self) -> str:
        """Return the version-controlled prompt identifier."""

    def assist(self, request: AssistanceRequest) -> AssistanceAction:
        """Interpret the request and return a structured assistance action."""


def validate_assistance_action(
    action: AssistanceAction,
    interaction: ReadOnlyJsonObject,
) -> AssistanceAction:
    """Validate proposed values against the current interaction schema.

    Args:
        action: Structured action returned by an assistant implementation.
        interaction: Current interaction returned by the journey service.

    Returns:
        The validated action.

    Raises:
        InteractionAssistantError: If a proposed field or value is not permitted by
            the current interaction schema.
    """
    if action.type != "propose_values":
        return action

    raw_schema = interaction.get("input_schema")
    if not isinstance(raw_schema, Mapping):
        msg = "Current interaction input_schema must be an object"
        raise InteractionAssistantError(msg)
    raw_properties = raw_schema.get("properties")
    if not isinstance(raw_properties, Mapping):
        msg = "Current interaction input_schema properties must be an object"
        raise InteractionAssistantError(msg)

    for field_name, value in action.values.items():
        raw_property = raw_properties.get(field_name)
        if not isinstance(raw_property, Mapping):
            msg = f"Assistant proposed field {field_name!r} outside the current schema"
            raise InteractionAssistantError(msg)
        if not _value_matches_property(value, raw_property):
            msg = (
                f"Assistant value for {field_name!r} does not match the current "
                "field schema"
            )
            raise InteractionAssistantError(msg)
    return action


def _value_matches_property(value: JsonScalar, property_schema: Mapping[str, Any]) -> bool:
    raw_type = property_schema.get("type")
    if raw_type is None:
        permitted_types: set[str] | None = None
    elif isinstance(raw_type, str):
        permitted_types = {raw_type}
    elif isinstance(raw_type, list) and all(isinstance(item, str) for item in raw_type):
        permitted_types = set(raw_type)
    else:
        return False

    if permitted_types is not None and not _matches_any_type(value, permitted_types):
        return False

    enum_values = property_schema.get("enum")
    return not isinstance(enum_values, list) or value in enum_values


def _matches_any_type(value: JsonScalar, permitted_types: set[str]) -> bool:
    if value is None:
        return "null" in permitted_types
    if isinstance(value, bool):
        return "boolean" in permitted_types
    if isinstance(value, int):
        return "integer" in permitted_types or "number" in permitted_types
    if isinstance(value, float):
        return "number" in permitted_types
    return "string" in permitted_types
