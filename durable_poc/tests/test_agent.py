"""Tests for the Strands agent composition layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from agent.agent import PROMPT_PATH, WorkflowAgent


# ---------------------------------------------------------------------------
# Fakes (reuse shapes from test_agent_tools)
# ---------------------------------------------------------------------------


@dataclass
class FakeWorkflowHandle:
    id: str
    query_responses: dict[str, Any] = field(default_factory=dict)
    update_calls: list[dict[str, Any]] = field(default_factory=list)

    async def query(self, query_name: str) -> Any:
        return self.query_responses.get(query_name)

    async def execute_update(self, update_name: str, arg: Any) -> None:
        self.update_calls.append({"update_name": update_name, "arg": arg})


@dataclass
class FakeWorkflowExecution:
    id: str
    status: str


class FakeWorkflowListIterator:
    def __init__(self, executions: list[FakeWorkflowExecution]) -> None:
        self._executions = executions
        self._index = 0

    def __aiter__(self) -> "FakeWorkflowListIterator":
        return self

    async def __anext__(self) -> FakeWorkflowExecution:
        if self._index >= len(self._executions):
            raise StopAsyncIteration
        execution = self._executions[self._index]
        self._index += 1
        return execution


class FakeTemporalClient:
    def __init__(self) -> None:
        self.started_workflows: list[dict[str, Any]] = []
        self.handles: dict[str, FakeWorkflowHandle] = {}
        self.workflow_executions: list[FakeWorkflowExecution] = []

    async def start_workflow(
        self, workflow: str, *, arg: Any, id: str, task_queue: str
    ) -> FakeWorkflowHandle:
        self.started_workflows.append(
            {"workflow": workflow, "arg": arg, "id": id, "task_queue": task_queue}
        )
        handle = FakeWorkflowHandle(id=id)
        self.handles[id] = handle
        return handle

    def get_workflow_handle(self, workflow_id: str) -> FakeWorkflowHandle:
        return self.handles[workflow_id]

    def list_workflows(self, query: str) -> FakeWorkflowListIterator:
        return FakeWorkflowListIterator(self.workflow_executions)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def test_system_prompt_file_exists() -> None:
    """The system prompt file must exist at the expected path."""
    assert PROMPT_PATH.exists()


def test_system_prompt_contains_integrity_instructions() -> None:
    """The prompt must instruct the agent not to skip or invent workflow steps."""
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "workflow" in content.lower()
    assert "skip" in content.lower() or "deviate" in content.lower()
    assert "submit_input" in content or "submit" in content.lower()


# ---------------------------------------------------------------------------
# Tool closures
# ---------------------------------------------------------------------------


def test_agent_exposes_expected_tool_names() -> None:
    """The agent is constructed with the correct set of tool functions."""
    temporal_client = FakeTemporalClient()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)

    agent = WorkflowAgent(
        temporal_client=temporal_client,
        http_client=http_client,
        workflow_server_url="http://localhost:8080",
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name="eu-west-2",
    )

    tool_names = agent.tool_names()
    assert "get_workflow_definition" in tool_names
    assert "start_workflow" in tool_names
    assert "get_workflow_state" in tool_names
    assert "submit_input" in tool_names
    assert "list_active_workflows" in tool_names


@pytest.mark.asyncio
async def test_get_workflow_state_tool_delegates_to_tools_module() -> None:
    """The get_workflow_state tool closure reaches the underlying function."""
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-1",
        query_responses={
            "awaiting": {"token": "tkn_1", "prompt": "Name?", "schema": {"kind": "string"}},
            "transcript": [],
        },
    )
    temporal_client.handles["wf-1"] = handle

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    http_client = httpx.AsyncClient(transport=transport)

    agent = WorkflowAgent(
        temporal_client=temporal_client,
        http_client=http_client,
        workflow_server_url="http://localhost:8080",
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name="eu-west-2",
    )

    result = await agent.call_tool("get_workflow_state", workflow_id="wf-1")
    assert result["awaiting"]["token"] == "tkn_1"


@pytest.mark.asyncio
async def test_submit_input_tool_delegates_and_returns_new_state() -> None:
    """The submit_input tool closure submits and returns the new workflow state."""
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-1",
        query_responses={
            "awaiting": {"token": "tkn_2", "prompt": "Next step", "schema": {"kind": "string"}},
            "transcript": [],
        },
    )
    temporal_client.handles["wf-1"] = handle

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    http_client = httpx.AsyncClient(transport=transport)

    agent = WorkflowAgent(
        temporal_client=temporal_client,
        http_client=http_client,
        workflow_server_url="http://localhost:8080",
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name="eu-west-2",
    )

    result = await agent.call_tool("submit_input", workflow_id="wf-1", token="tkn_1", value=True)
    assert len(handle.update_calls) == 1
    assert handle.update_calls[0]["arg"].token == "tkn_1"
    assert handle.update_calls[0]["arg"].value is True
    assert result["awaiting"]["token"] == "tkn_2"
