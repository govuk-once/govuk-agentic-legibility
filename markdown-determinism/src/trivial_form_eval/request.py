import os
from dataclasses import dataclass, field
from typing import Any

from trivial_form_eval.fixture import Fixture

DEFAULT_MODEL = "bedrock/converse/eu.anthropic.claude-haiku-4-5-20251001-v1:0"

# Kept only so existing imports and historical tests do not break.
# build_request() does not use this constant; it derives the name from the fixture.
EXPECTED_TOOL_NAME = "submit_contact_details"


@dataclass(frozen=True)
class RequestConfig:
    model: str
    messages: list[dict[str, str]]
    tools: list[dict[str, Any]]
    tool_choice: dict[str, Any]
    model_parameters: dict[str, Any] = field(default_factory=dict)

    def as_litellm_kwargs(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.messages,
            "tools": self.tools,
            "tool_choice": self.tool_choice,
            **self.model_parameters,
        }

    def as_saved_json(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.messages,
            "tools": self.tools,
            "tool_choice": self.tool_choice,
            "model_parameters": self.model_parameters,
        }


def resolve_model(cli_model: str | None) -> str:
    return cli_model or os.getenv("LITELLM_MODEL") or DEFAULT_MODEL


def build_request(
    fixture: Fixture,
    model: str,
    model_parameters: dict[str, Any] | None = None,
) -> RequestConfig:
    return RequestConfig(
        model=model,
        messages=[
            {"role": "system", "content": fixture.instructions_text},
            {"role": "user", "content": fixture.case_text},
        ],
        tools=[fixture.tool_schema],
        tool_choice={
            "type": "function",
            "function": {"name": fixture.expected_tool_name},
        },
        model_parameters=model_parameters or {},
    )
