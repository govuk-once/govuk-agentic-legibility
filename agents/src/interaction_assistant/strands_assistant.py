"""Strands and Amazon Bedrock implementation of interaction assistance."""

from __future__ import annotations

import json
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel

from agents.src.interaction_assistant.assistant import (
    AssistanceAction,
    AssistanceRequest,
    InteractionAssistantError,
)

PROMPT_ID = "interaction-value-proposals-v1"
PROMPT_PATH = Path(__file__).with_name("prompts") / "value_proposals.txt"


class StrandsInteractionAssistant:
    """Use one Bedrock model to propose values for the current interaction.

    Args:
        model_id: Bedrock model or inference-profile identifier.
        region_name: AWS region used by the Bedrock model provider.
        system_prompt: Optional prompt override used by tests or experiments.
    """

    def __init__(
        self,
        *,
        model_id: str,
        region_name: str,
        system_prompt: str | None = None,
    ) -> None:
        self._model_id = model_id
        self._system_prompt = system_prompt or PROMPT_PATH.read_text(encoding="utf-8")
        self._model = BedrockModel(
            model_id=model_id,
            region_name=region_name,
            temperature=0.0,
        )

    @property
    def model_id(self) -> str:
        """Return the configured Bedrock model identifier."""
        return self._model_id

    @property
    def prompt_id(self) -> str:
        """Return the version-controlled prompt identifier."""
        return PROMPT_ID

    def assist(self, request: AssistanceRequest) -> AssistanceAction:
        """Return a structured proposal or no-safe-suggestion action.

        Args:
            request: Conversation context and current service interaction.

        Returns:
            Structured assistance action.

        Raises:
            InteractionAssistantError: If Strands or Bedrock cannot return a valid
                structured action.
        """
        agent = Agent(
            model=self._model,
            system_prompt=self._system_prompt,
            callback_handler=None,
        )
        try:
            return agent.structured_output(
                AssistanceAction,
                _request_prompt(request),
            )
        except Exception as exc:
            msg = (
                "Interaction assistant could not produce a valid structured action: "
                f"{exc}"
            )
            raise InteractionAssistantError(msg) from exc


def _request_prompt(request: AssistanceRequest) -> str:
    payload = {
        "conversation": [
            message.model_dump(mode="json") for message in request.conversation
        ],
        "latest_user_message": request.user_message,
        "current_interaction": request.interaction,
    }
    return (
        "Interpret the latest user message for the current service interaction. "
        "Use only the supplied context.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
