"""Tests for the agent tool functions that bridge to Temporal and the workflow server."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from agent.tools import (
    WorkflowServerError,
    get_workflow_definition,
    get_workflow_state,
    list_active_workflows,
    start_workflow,
    submit_input,
)


@dataclass
class FakeWorkflowStatus:
    name: str = "RUNNING"


@dataclass
class FakeWorkflowDescription:
    status: FakeWorkflowStatus = field(default_factory=FakeWorkflowStatus)


@dataclass
class FakeWorkflowHandle:
    """Minimal Temporal workflow handle for testing."""

    id: str
    query_responses: dict[str, Any] = field(default_factory=dict)
    update_calls: list[dict[str, Any]] = field(default_factory=list)
    update_error: Exception | None = None
    execution_status: str = "RUNNING"

    async def describe(self) -> FakeWorkflowDescription:
        return FakeWorkflowDescription(
            status=FakeWorkflowStatus(name=self.execution_status)
        )

    async def query(self, query_name: str) -> Any:
        return self.query_responses.get(query_name)

    async def execute_update(self, update_name: str, arg: Any) -> None:
        if self.update_error:
            raise self.update_error
        self.update_calls.append({"update_name": update_name, "arg": arg})


@dataclass
class FakeWorkflowExecution:
    """Minimal Temporal workflow execution info for list results."""

    id: str
    status: str


class FakeWorkflowListIterator:
    """Async iterator over fake workflow executions."""

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
    """Minimal Temporal client for testing."""

    def __init__(self) -> None:
        self.started_workflows: list[dict[str, Any]] = []
        self.handles: dict[str, FakeWorkflowHandle] = {}
        self.workflow_executions: list[FakeWorkflowExecution] = []

    async def start_workflow(
        self,
        workflow: str,
        *,
        arg: Any,
        id: str,
        task_queue: str,
    ) -> FakeWorkflowHandle:
        self.started_workflows.append(
            {"workflow": workflow, "arg": arg, "id": id, "task_queue": task_queue}
        )
        handle = FakeWorkflowHandle(id=id)
        self.handles[id] = handle
        return handle

    def get_workflow_handle(self, workflow_id: str) -> FakeWorkflowHandle:
        if workflow_id not in self.handles:
            self.handles[workflow_id] = FakeWorkflowHandle(id=workflow_id)
        return self.handles[workflow_id]

    def list_workflows(self, query: str) -> FakeWorkflowListIterator:
        return FakeWorkflowListIterator(self.workflow_executions)


# ---------------------------------------------------------------------------
# get_workflow_definition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_workflow_definition_returns_parsed_definition() -> None:
    """A successful fetch returns the workflow definition dict."""
    definition = {
        "workflow_id": 1,
        "schema": "sfsm/0.2",
        "id": "dvla.change_of_address",
        "version": "0.2.0",
        "entry": "main",
        "processes": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:8080/api/v1/workflows/1"
        return httpx.Response(200, json=definition)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await get_workflow_definition(
            workflow_id=1,
            http_client=client,
            base_url="http://localhost:8080",
        )

    assert result == definition


@pytest.mark.asyncio
async def test_get_workflow_definition_raises_on_http_error() -> None:
    """An HTTP error from the workflow server surfaces as WorkflowServerError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(WorkflowServerError, match="404"):
            await get_workflow_definition(
                workflow_id=99,
                http_client=client,
                base_url="http://localhost:8080",
            )


# ---------------------------------------------------------------------------
# start_workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_workflow_fetches_definition_and_starts() -> None:
    """Starting a workflow fetches definition then starts it with unique prefix."""
    temporal_client = FakeTemporalClient()
    definition = {
        "schema": "sfsm/0.2",
        "id": "dvla.change_of_address",
        "version": "0.2.0",
        "entry": "main",
        "executor": {},
        "processes": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:8080/api/v1/workflows/1"
        return httpx.Response(200, json=definition)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        workflow_id = await start_workflow(
            workflow_id=1,
            http_client=client,
            base_url="http://localhost:8080",
            temporal_client=temporal_client,
            task_queue="sfsm-queue",
        )

    assert workflow_id.startswith("sfsm-dvla.change_of_address-")
    assert len(temporal_client.started_workflows) == 1
    started = temporal_client.started_workflows[0]
    assert started["workflow"] == "SFSMInterpreter"
    assert started["arg"] == definition
    assert started["task_queue"] == "sfsm-queue"


# ---------------------------------------------------------------------------
# get_workflow_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_workflow_state_returns_awaiting_status_and_transcript() -> None:
    """When the workflow is waiting for input, state includes full context."""
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-1",
        execution_status="RUNNING",
        query_responses={
            "awaiting": {
                "token": "tkn_1",
                "prompt": "Enter your postcode",
                "schema": {"kind": "string"},
            },
            "transcript": [
                {"step": 1, "timestamp": "2024-01-01T00:00:00", "message": "Started"}
            ],
        },
    )
    temporal_client.handles["wf-1"] = handle

    state = await get_workflow_state(
        workflow_id="wf-1",
        temporal_client=temporal_client,
    )

    assert state["workflow_id"] == "wf-1"
    assert state["status"] == "RUNNING"
    assert state["awaiting"] is not None
    assert state["awaiting"]["token"] == "tkn_1"
    assert state["awaiting"]["prompt"] == "Enter your postcode"
    assert len(state["transcript"]) == 1


@pytest.mark.asyncio
async def test_get_workflow_state_returns_none_awaiting_when_processing() -> None:
    """When the workflow is not waiting for input, awaiting is None."""
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-2",
        execution_status="COMPLETED",
        query_responses={"awaiting": None, "transcript": []},
    )
    temporal_client.handles["wf-2"] = handle

    state = await get_workflow_state(
        workflow_id="wf-2",
        temporal_client=temporal_client,
    )

    assert state["status"] == "COMPLETED"
    assert state["awaiting"] is None
    assert state["transcript"] == []


# ---------------------------------------------------------------------------
# submit_input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_input_calls_execute_update_and_returns_new_state() -> None:
    """A valid submission advances the workflow and returns the new state."""
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-1",
        query_responses={
            "awaiting": {
                "token": "tkn_2",
                "prompt": "Enter your postcode",
                "schema": {"kind": "string"},
            },
            "transcript": [
                {"step": 1, "timestamp": "2024-01-01T00:00:00", "message": "Confirmed"}
            ],
        },
    )
    temporal_client.handles["wf-1"] = handle

    result = await submit_input(
        workflow_id="wf-1",
        token="tkn_1",
        value="SW1A 2AA",
        temporal_client=temporal_client,
    )

    assert len(handle.update_calls) == 1
    call = handle.update_calls[0]
    assert call["update_name"] == "submit_input"
    assert call["arg"].token == "tkn_1"
    assert call["arg"].value == "SW1A 2AA"
    assert result["awaiting"]["token"] == "tkn_2"
    assert result["awaiting"]["prompt"] == "Enter your postcode"
    assert len(result["transcript"]) == 1


@pytest.mark.asyncio
async def test_submit_input_surfaces_validation_error() -> None:
    """A token mismatch from the workflow validator propagates to the caller."""
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-1",
        update_error=Exception("Token mismatch. Expected tkn_2"),
    )
    temporal_client.handles["wf-1"] = handle

    with pytest.raises(Exception, match="Token mismatch"):
        await submit_input(
            workflow_id="wf-1",
            token="tkn_1",
            value="anything",
            temporal_client=temporal_client,
        )


# ---------------------------------------------------------------------------
# list_active_workflows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_workflows_returns_running_workflows() -> None:
    """Returns summaries for running SFSMInterpreter workflows."""
    temporal_client = FakeTemporalClient()
    temporal_client.workflow_executions = [
        FakeWorkflowExecution(id="sfsm-dvla.change_of_address-0.2.0", status="RUNNING"),
        FakeWorkflowExecution(id="sfsm-dvla.change_of_address-0.2.1", status="RUNNING"),
    ]

    result = await list_active_workflows(temporal_client=temporal_client)

    assert len(result) == 2
    assert result[0] == {"id": "sfsm-dvla.change_of_address-0.2.0", "status": "RUNNING"}
    assert result[1] == {"id": "sfsm-dvla.change_of_address-0.2.1", "status": "RUNNING"}


@pytest.mark.asyncio
async def test_list_active_workflows_returns_empty_when_none_running() -> None:
    """Returns an empty list when no workflows are active."""
    temporal_client = FakeTemporalClient()
    temporal_client.workflow_executions = []

    result = await list_active_workflows(temporal_client=temporal_client)

    assert result == []
