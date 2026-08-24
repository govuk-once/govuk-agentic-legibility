"""Strands agent composition for the durable FSM workflow executor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from strands import Agent, tool
from strands.models import BedrockModel

from agent import tools as tool_functions

PROMPT_PATH = Path(__file__).with_name("prompts") / "system.txt"


class WorkflowAgent:
    """Composes the Strands agent with workflow tools bound to live dependencies.

    Args:
        temporal_client: A Temporal client instance.
        http_client: An httpx async client for the workflow server.
        workflow_server_url: Base URL of the workflow definition server.
        model_id: Bedrock model or inference-profile identifier.
        region_name: AWS region for the Bedrock model.
    """

    def __init__(
        self,
        *,
        temporal_client: Any,
        http_client: httpx.AsyncClient,
        workflow_server_url: str,
        model_id: str,
        region_name: str,
    ) -> None:
        self._temporal_client = temporal_client
        self._http_client = http_client
        self._workflow_server_url = workflow_server_url
        self._system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self._model = BedrockModel(
            model_id=model_id,
            region_name=region_name,
            temperature=0.0,
        )
        self._tools = self._build_tools()

    def tool_names(self) -> list[str]:
        """Return the names of all tools available to the agent."""
        return [t.__name__ for t in self._tools]

    async def call_tool(self, name: str, **kwargs: Any) -> Any:
        """Invoke a tool closure directly by name. Used for testing."""
        for t in self._tools:
            if t.__name__ == name:
                return await t(**kwargs)
        raise ValueError(f"Unknown tool: {name}")

    def respond(self, user_message: str) -> str:
        """Send a user message to the agent and return the text response.

        Args:
            user_message: The user's natural language input.

        Returns:
            The agent's text response.
        """
        agent = Agent(
            model=self._model,
            system_prompt=self._system_prompt,
            tools=self._tools,
            callback_handler=None,
        )
        result = agent(user_message)
        return str(result)

    def _build_tools(self) -> list[Any]:
        temporal_client = self._temporal_client
        http_client = self._http_client
        workflow_server_url = self._workflow_server_url

        @tool
        async def get_workflow_definition(workflow_id: int) -> dict[str, Any]:
            """Fetch a workflow definition from the server by its numeric ID.

            Args:
                workflow_id: The numeric workflow ID.
            """
            return await tool_functions.get_workflow_definition(
                workflow_id=workflow_id,
                http_client=http_client,
                base_url=workflow_server_url,
            )

        @tool
        async def start_workflow(definition: dict[str, Any]) -> dict[str, str]:
            """Start a new workflow execution on Temporal.

            Args:
                definition: The full workflow definition dict.
            """
            workflow_id = await tool_functions.start_workflow(
                definition=definition,
                temporal_client=temporal_client,
                task_queue="sfsm-queue",
            )
            return {"workflow_id": workflow_id}

        @tool
        async def get_workflow_state(workflow_id: str) -> dict[str, Any]:
            """Query the current state of a running workflow.

            Args:
                workflow_id: The Temporal workflow ID.
            """
            return await tool_functions.get_workflow_state(
                workflow_id=workflow_id,
                temporal_client=temporal_client,
            )

        @tool
        async def submit_input(workflow_id: str, token: str, value: Any) -> dict[str, Any]:
            """Submit user input to a workflow and return the new workflow state.

            Args:
                workflow_id: The Temporal workflow ID.
                token: The input token from the awaiting state.
                value: The structured value to submit.
            """
            return await tool_functions.submit_input(
                workflow_id=workflow_id,
                token=token,
                value=value,
                temporal_client=temporal_client,
            )

        @tool
        async def list_active_workflows() -> list[dict[str, str]]:
            """List running workflows that the user may want to resume."""
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
