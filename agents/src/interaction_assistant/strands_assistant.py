"""Strands and Amazon Bedrock implementation of interaction assistance."""

from __future__ import annotations

import json
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel

from agents.src.interaction_assistant.assistant import (
    AssistanceActions,
    AssistanceContext,
    AssistanceRequest,
    AssistanceResult,
    InteractionAssistantError,
)
from agents.src.workflow_executor.guidance import GuidanceReference
from agents.src.workflow_executor.types import JsonObject

PROMPT_ID = "interaction-assistance-v5"
PROMPT_PATH = Path(__file__).with_name("prompts") / "value_proposals.txt"


class StrandsInteractionAssistant:
    """Use one Bedrock model for bounded support at the current interaction.

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

    def assist(
        self,
        request: AssistanceRequest,
        context: AssistanceContext,
    ) -> AssistanceResult:
        """Return structured assistance and observed guidance retrievals.

        Args:
            request: Conversation context and current service interaction.
            context: Run-scoped bounded guidance client and trace recorder.

        Returns:
            Structured model action plus guidance actually retrieved by tools.

        Raises:
            InteractionAssistantError: If Strands or Bedrock cannot return a valid
                structured action.
        """
        retrieved_documents: dict[str, GuidanceReference] = {}

        @tool
        def list_journey_guidance() -> JsonObject:
            """List approved guidance topics for the active service journey."""
            arguments: JsonObject = {}
            context.tool_recorder.record_agent_tool_requested(
                tool="list_journey_guidance",
                arguments=arguments,
            )
            try:
                directory = context.guidance.list_guidance(context.journey_id)
            except Exception as exc:
                context.tool_recorder.record_agent_tool_failed(
                    tool="list_journey_guidance",
                    arguments=arguments,
                    error=str(exc),
                )
                raise

            result = directory.model_dump(mode="json")
            context.tool_recorder.record_agent_tool_completed(
                tool="list_journey_guidance",
                arguments=arguments,
                result=result,
            )
            return {
                "status": "success",
                "content": [{"json": result}],
            }

        @tool
        def get_journey_guidance(topic_id: str) -> JsonObject:
            """Retrieve one approved Markdown guidance document.

            Args:
                topic_id: Topic ID returned by ``list_journey_guidance``.
            """
            arguments: JsonObject = {"topic_id": topic_id}
            context.tool_recorder.record_agent_tool_requested(
                tool="get_journey_guidance",
                arguments=arguments,
            )
            try:
                document = context.guidance.get_guidance(
                    context.journey_id,
                    topic_id,
                )
            except Exception as exc:
                context.tool_recorder.record_agent_tool_failed(
                    tool="get_journey_guidance",
                    arguments=arguments,
                    error=str(exc),
                )
                raise

            reference = GuidanceReference.from_document(document)
            retrieved_documents[reference.id] = reference
            trace_result = reference.model_dump(mode="json")
            context.tool_recorder.record_agent_tool_completed(
                tool="get_journey_guidance",
                arguments=arguments,
                result=trace_result,
            )
            return {
                "status": "success",
                "content": [{"json": document.model_dump(mode="json")}],
            }

        agent = Agent(
            model=self._model,
            system_prompt=self._system_prompt,
            tools=[list_journey_guidance, get_journey_guidance],
            callback_handler=None,
        )
        try:
            result = agent(
                _request_prompt(request),
                structured_output_model=AssistanceActions,
            )
            actions = result.structured_output
            if not isinstance(actions, AssistanceActions):
                msg = "Interaction assistant did not return structured output"
                raise InteractionAssistantError(msg)
        except Exception as exc:
            msg = (
                "Interaction assistant could not produce a valid structured action: "
                f"{exc}"
            )
            raise InteractionAssistantError(msg) from exc

        return AssistanceResult(
            actions=actions.actions,
            retrieved_guidance=list(retrieved_documents.values()),
        )


def _request_prompt(request: AssistanceRequest) -> str:
    payload = {
        "trigger": request.trigger.model_dump(mode="json"),
        "conversation": [
            message.model_dump(mode="json") for message in request.conversation
        ],
        "current_interaction": request.interaction,
    }
    return (
        "Support the user at the current service interaction. The invocation trigger "
        "states why you were called and must determine what you respond to. For an "
        "interaction_opened trigger, only propose values for the newly opened form and "
        "do not answer questions from earlier turns again. For a user_message_added "
        "trigger, respond specifically to trigger.message. If that new message asks a "
        "journey question, use the approved guidance tools before answering. A new user "
        "message may require both an answer and a value proposal. Return "
        "answer_journey_question followed by propose_values when the new message asks a "
        "journey question and also clearly expresses a value for the current form. Do "
        "not claim to submit or confirm values; proposals still require user review. "
        "Use later explicit corrections in preference to earlier values.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
