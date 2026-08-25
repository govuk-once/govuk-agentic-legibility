"""Strands agent composition for the durable FSM workflow executor."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
from strands import Agent, tool
from strands.models import BedrockModel
from temporalio.client import Client as TemporalClient

from agent import tools as tool_functions

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).with_name("prompts") / "system.txt"


def build_contextual_prompt(
    user_message: str, *, context: dict[str, Any] | None
) -> str:
    """Build the agent prompt with HATEOAS continuation context.

    When context is provided, the agent receives the current workflow state
    alongside the user message — eliminating the need for conversation memory.

    Args:
        user_message: The user's natural language input.
        context: The current workflow state (workflow_id + awaiting), or None.

    Returns:
        The formatted prompt string for the agent.
    """
    if context is None:
        return user_message

    workflow_id = context.get("workflow_id", "unknown")
    awaiting = context.get("awaiting")

    if awaiting:
        state_description = (
            f"Active workflow: {workflow_id}\n"
            f"Currently awaiting input:\n"
            f"  token: {awaiting['token']}\n"
            f"  prompt: {awaiting['prompt']}\n"
            f"  schema: {json.dumps(awaiting.get('schema', {}))}\n"
        )
    else:
        state_description = (
            f"Active workflow: {workflow_id}\n"
            f"The workflow is not currently awaiting input (it may be processing or completed).\n"
        )

    return f"{state_description}\nUser message: {user_message}"


_TRUTHY = frozenset({"true", "yes", "y", "yeah", "sure", "confirm", "1"})


def _coerce_value(value: Any, session_state: dict[str, Any] | None) -> Any:
    """Coerce a tool argument to the type the workflow schema expects.

    LLMs sometimes pass values as the wrong JSON type (e.g. "Yes" instead of
    true, or "42" instead of 42). This uses the known schema from session state
    to coerce to the correct Python type before submission to Temporal.
    """
    if session_state is None:
        return value
    awaiting = session_state.get("awaiting")
    if not awaiting:
        return value
    schema = awaiting.get("schema", {})
    kind = schema.get("kind")

    if kind == "boolean" and not isinstance(value, bool):
        return str(value).strip().lower() in _TRUTHY

    if kind == "string" and not isinstance(value, str):
        return str(value)

    if kind == "object" and isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return value


class WorkflowAgent:
    """Composes the Strands agent with workflow tools.

    The agent exists independently of Temporal. A Temporal connection is
    established lazily on the first tool call that requires it, ensuring the
    gRPC channel binds to the active event loop (e.g. Gradio's uvicorn loop).

    Args:
        workflow_server_url: Base URL of the workflow definition server.
        model_id: Bedrock model or inference-profile identifier.
        region_name: AWS region for the Bedrock model.
        temporal_address: Temporal server address (connected lazily).
        task_queue: Temporal task queue for workflow executions.
    """

    def __init__(
        self,
        *,
        workflow_server_url: str,
        model_id: str,
        region_name: str,
        temporal_address: str = "localhost:7233",
        task_queue: str = "sfsm-queue",
    ) -> None:
        self._workflow_server_url = workflow_server_url
        self._temporal_address = temporal_address
        self._task_queue = task_queue
        self._temporal_client: TemporalClient | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self._model = BedrockModel(
            model_id=model_id,
            region_name=region_name,
            temperature=0.0,
        )
        self._session_state: dict[str, Any] | None = None
        self._tools = self._build_tools()
        self._agent = Agent(
            model=self._model,
            system_prompt=self._system_prompt,
            tools=self._tools,
            callback_handler=None,
        )

    async def _get_temporal_client(self) -> TemporalClient:
        if self._temporal_client is None:
            self._temporal_client = await TemporalClient.connect(
                self._temporal_address
            )
        return self._temporal_client

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    @property
    def session_state(self) -> dict[str, Any] | None:
        """The current HATEOAS continuation state, updated by tool calls."""
        return self._session_state

    def tool_names(self) -> list[str]:
        """Return the names of all tools available to the agent."""
        return [t.__name__ for t in self._tools]

    async def call_tool(self, name: str, **kwargs: Any) -> Any:
        """Invoke a tool closure directly by name. Used for testing."""
        for t in self._tools:
            if t.__name__ == name:
                return await t(**kwargs)
        raise ValueError(f"Unknown tool: {name}")

    async def respond(
        self, user_message: str, *, context: dict[str, Any] | None = None
    ) -> str:
        """Send a user message to the agent and return the text response.

        The agent instance is long-lived, maintaining conversation history
        across turns. The optional context provides the authoritative workflow
        state from Temporal (HATEOAS continuation).

        Args:
            user_message: The user's natural language input.
            context: Optional HATEOAS continuation state (workflow_id + awaiting).

        Returns:
            The agent's text response.
        """
        prompt = build_contextual_prompt(user_message, context=context)
        result = await self._agent.invoke_async(prompt)
        return str(result)

    def _update_session_state(
        self, workflow_id: str, state: dict[str, Any]
    ) -> None:
        self._session_state = {
            "workflow_id": workflow_id,
            "awaiting": state.get("awaiting"),
        }

    def _build_tools(self) -> list[Any]:
        owner = self

        @tool
        async def get_workflow_definition(workflow_id: int) -> dict[str, Any]:
            """Fetch a workflow definition from the server by its numeric ID.

            Args:
                workflow_id: The numeric workflow ID.
            """
            http_client = await owner._get_http_client()
            return await tool_functions.get_workflow_definition(
                workflow_id=workflow_id,
                http_client=http_client,
                base_url=owner._workflow_server_url,
            )

        @tool
        async def start_workflow(workflow_id: int) -> dict[str, Any]:
            """Fetch a workflow definition by numeric ID and start it on Temporal.

            Args:
                workflow_id: The numeric workflow ID from the workflow server.
            """
            http_client = await owner._get_http_client()
            temporal_client = await owner._get_temporal_client()
            temporal_workflow_id = await tool_functions.start_workflow(
                workflow_id=workflow_id,
                http_client=http_client,
                base_url=owner._workflow_server_url,
                temporal_client=temporal_client,
                task_queue=owner._task_queue,
            )
            state = await tool_functions.get_workflow_state(
                workflow_id=temporal_workflow_id, temporal_client=temporal_client
            )
            owner._update_session_state(temporal_workflow_id, state)
            return {"workflow_id": temporal_workflow_id, **state}

        @tool
        async def get_workflow_state(workflow_id: str) -> dict[str, Any]:
            """Query the current state of a running workflow.

            Args:
                workflow_id: The Temporal workflow ID.
            """
            temporal_client = await owner._get_temporal_client()
            state = await tool_functions.get_workflow_state(
                workflow_id=workflow_id,
                temporal_client=temporal_client,
            )
            owner._update_session_state(workflow_id, state)
            return state

        @tool
        async def submit_input(workflow_id: str, token: str, value: Any) -> dict[str, Any]:
            """Submit user input to a workflow and return the new workflow state.

            Args:
                workflow_id: The Temporal workflow ID.
                token: The input token from the awaiting state.
                value: The structured value to submit.
            """
            value = _coerce_value(value, owner._session_state)
            logger.info(
                "submit_input called: workflow_id=%r, token=%r, value=%r (type=%s)",
                workflow_id, token, value, type(value).__name__,
            )
            try:
                temporal_client = await owner._get_temporal_client()
                state = await tool_functions.submit_input(
                    workflow_id=workflow_id,
                    token=token,
                    value=value,
                    temporal_client=temporal_client,
                )
                owner._update_session_state(workflow_id, state)
                return state
            except Exception:
                logger.exception("submit_input failed")
                raise

        @tool
        async def list_active_workflows() -> list[dict[str, str]]:
            """List running workflows that the user may want to resume."""
            temporal_client = await owner._get_temporal_client()
            return await tool_functions.list_active_workflows(
                temporal_client=temporal_client,
            )

        return [
            get_workflow_definition,
            start_workflow,
            get_workflow_state,
            submit_input,
            list_active_workflows,
        ]
