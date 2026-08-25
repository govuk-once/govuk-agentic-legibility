"""Tests for the Strands agent composition layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from agent.agent import PROMPT_PATH, WorkflowAgent, _coerce_value, build_contextual_prompt


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
# Value coercion
# ---------------------------------------------------------------------------


def _state_with_schema(kind: str, **extra: Any) -> dict[str, Any]:
    schema = {"kind": kind, **extra}
    return {"workflow_id": "wf-1", "awaiting": {"token": "t", "prompt": "?", "schema": schema}}


def test_coerce_boolean_from_string_yes() -> None:
    assert _coerce_value("Yes", _state_with_schema("boolean")) is True


def test_coerce_boolean_from_string_no() -> None:
    assert _coerce_value("no", _state_with_schema("boolean")) is False


def test_coerce_boolean_from_string_true() -> None:
    assert _coerce_value("true", _state_with_schema("boolean")) is True


def test_coerce_boolean_passthrough_when_already_bool() -> None:
    assert _coerce_value(False, _state_with_schema("boolean")) is False


def test_coerce_string_from_non_string() -> None:
    assert _coerce_value(42, _state_with_schema("string")) == "42"


def test_coerce_string_passthrough() -> None:
    assert _coerce_value("SW1A 2AA", _state_with_schema("string")) == "SW1A 2AA"


def test_coerce_object_from_json_string() -> None:
    result = _coerce_value('{"ref": "photo.png"}', _state_with_schema("object"))
    assert result == {"ref": "photo.png"}


def test_coerce_object_passthrough_when_already_dict() -> None:
    val = {"ref": "photo.png", "content_type": "image/png"}
    assert _coerce_value(val, _state_with_schema("object")) == val


def test_coerce_no_state_returns_unchanged() -> None:
    assert _coerce_value("Yes", None) == "Yes"


def test_coerce_no_awaiting_returns_unchanged() -> None:
    state = {"workflow_id": "wf-1", "awaiting": None}
    assert _coerce_value("Yes", state) == "Yes"


# ---------------------------------------------------------------------------
# Contextual prompt building
# ---------------------------------------------------------------------------


def test_build_contextual_prompt_without_state() -> None:
    """Without workflow state, the prompt is just the user message."""
    result = build_contextual_prompt("Hello", context=None)
    assert result == "Hello"


def test_build_contextual_prompt_with_awaiting_state() -> None:
    """With active workflow state, the prompt includes continuation context."""
    context = {
        "workflow_id": "sfsm-dvla.change_of_address-0.2.0",
        "awaiting": {
            "token": "tkn_3",
            "prompt": "Please enter your new postcode.",
            "schema": {"kind": "string", "pattern": "[A-Z]{1,2}\\d[A-Z\\d]?\\s*\\d[A-Z]{2}"},
        },
    }
    result = build_contextual_prompt("SW1A 2AA", context=context)

    assert "sfsm-dvla.change_of_address-0.2.0" in result
    assert "tkn_3" in result
    assert "Please enter your new postcode." in result
    assert "SW1A 2AA" in result


def test_build_contextual_prompt_with_completed_workflow() -> None:
    """When awaiting is None, the context still includes the workflow ID."""
    context = {
        "workflow_id": "sfsm-dvla.change_of_address-0.2.0",
        "awaiting": None,
    }
    result = build_contextual_prompt("What happened?", context=context)

    assert "sfsm-dvla.change_of_address-0.2.0" in result
    assert "not currently awaiting" in result.lower() or "no pending" in result.lower()
    assert "What happened?" in result


# ---------------------------------------------------------------------------
# Helper to create agent with pre-injected fakes
# ---------------------------------------------------------------------------


def make_test_agent(
    temporal_client: FakeTemporalClient,
    http_handler: Any = None,
) -> WorkflowAgent:
    """Create a WorkflowAgent with fakes injected, bypassing lazy connection."""
    if http_handler is None:
        http_handler = lambda r: httpx.Response(200, json={})  # noqa: E731
    transport = httpx.MockTransport(http_handler)
    agent = WorkflowAgent(
        workflow_server_url="http://localhost:8080",
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name="eu-west-2",
    )
    agent._temporal_client = temporal_client
    agent._http_client = httpx.AsyncClient(transport=transport)
    return agent


# ---------------------------------------------------------------------------
# Tool closures
# ---------------------------------------------------------------------------


def test_agent_exposes_expected_tool_names() -> None:
    """The agent is constructed with the correct set of tool functions."""
    agent = make_test_agent(FakeTemporalClient())

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

    agent = make_test_agent(temporal_client)

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

    agent = make_test_agent(temporal_client)

    result = await agent.call_tool("submit_input", workflow_id="wf-1", token="tkn_1", value=True)
    assert len(handle.update_calls) == 1
    assert handle.update_calls[0]["arg"].token == "tkn_1"
    assert handle.update_calls[0]["arg"].value is True
    assert result["awaiting"]["token"] == "tkn_2"


# ---------------------------------------------------------------------------
# Session state updates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_workflow_updates_session_state() -> None:
    """Starting a workflow sets the session state with workflow_id and awaiting."""
    temporal_client = FakeTemporalClient()
    definition = {
        "schema": "sfsm/0.2",
        "id": "dvla.change_of_address",
        "version": "0.2.0",
        "entry": "main",
        "executor": {},
        "processes": {},
    }

    agent = make_test_agent(
        temporal_client,
        http_handler=lambda r: httpx.Response(200, json=definition),
    )

    assert agent.session_state is None
    await agent.call_tool("start_workflow", workflow_id=1)

    assert agent.session_state is not None
    assert agent.session_state["workflow_id"] == "sfsm-dvla.change_of_address-0.2.0"


@pytest.mark.asyncio
async def test_submit_input_updates_session_state() -> None:
    """Submitting input updates session state with the new awaiting info."""
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-1",
        query_responses={
            "awaiting": {"token": "tkn_2", "prompt": "Next?", "schema": {"kind": "boolean"}},
            "transcript": [{"step": 1, "timestamp": "t", "message": "Done"}],
        },
    )
    temporal_client.handles["wf-1"] = handle

    agent = make_test_agent(temporal_client)
    await agent.call_tool("submit_input", workflow_id="wf-1", token="tkn_1", value="yes")

    assert agent.session_state is not None
    assert agent.session_state["workflow_id"] == "wf-1"
    assert agent.session_state["awaiting"]["token"] == "tkn_2"


@pytest.mark.asyncio
async def test_get_workflow_state_updates_session_state() -> None:
    """Querying workflow state also updates session state."""
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-1",
        query_responses={
            "awaiting": {"token": "tkn_1", "prompt": "Name?", "schema": {"kind": "string"}},
            "transcript": [],
        },
    )
    temporal_client.handles["wf-1"] = handle

    agent = make_test_agent(temporal_client)
    await agent.call_tool("get_workflow_state", workflow_id="wf-1")

    assert agent.session_state is not None
    assert agent.session_state["workflow_id"] == "wf-1"
    assert agent.session_state["awaiting"]["token"] == "tkn_1"
