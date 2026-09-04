"""Unit tests for OpenTelemetry tracing instrumentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agent.agent import WorkflowAgent
from src.activities import CallParams, http_call
from src.telemetry import SessionSpanProcessor


# ---------------------------------------------------------------------------
# Module-level provider (OTEL only allows set_tracer_provider once per process)
# ---------------------------------------------------------------------------

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
trace.set_tracer_provider(_provider)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def otel_provider():
    """Clear the in-memory exporter before each test and yield it."""
    _exporter.clear()
    yield _exporter


# ---------------------------------------------------------------------------
# Fakes (mirrored from test_agent.py)
# ---------------------------------------------------------------------------


@dataclass
class FakeWorkflowStatus:
    name: str = "RUNNING"


@dataclass
class FakeWorkflowDescription:
    status: FakeWorkflowStatus = field(default_factory=FakeWorkflowStatus)


@dataclass
class FakeWorkflowHandle:
    id: str
    query_responses: dict[str, Any] = field(default_factory=dict)
    update_calls: list[dict[str, Any]] = field(default_factory=list)
    execution_status: str = "RUNNING"

    async def describe(self) -> FakeWorkflowDescription:
        return FakeWorkflowDescription(
            status=FakeWorkflowStatus(name=self.execution_status)
        )

    async def query(self, query_name: str) -> Any:
        return self.query_responses.get(query_name)

    async def execute_update(self, update_name: str, arg: Any) -> None:
        self.update_calls.append({"update_name": update_name, "arg": arg})


class FakeTemporalClient:
    def __init__(self) -> None:
        self.started_workflows: list[dict[str, Any]] = []
        self.handles: dict[str, FakeWorkflowHandle] = {}

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
        if workflow_id not in self.handles:
            self.handles[workflow_id] = FakeWorkflowHandle(id=workflow_id)
        return self.handles[workflow_id]


def _make_agent(
    temporal_client: FakeTemporalClient,
    http_handler: Any = None,
) -> WorkflowAgent:
    if http_handler is None:
        http_handler = lambda r: httpx.Response(200, json={})  # noqa: E731
    transport = httpx.MockTransport(http_handler)
    agent = WorkflowAgent(
        workflow_server_url="http://localhost:8080",
        model_id="anthropic.claude-sonnet-4-6",
        region_name="eu-west-2",
    )
    agent._temporal_client = temporal_client
    agent._http_client = httpx.AsyncClient(transport=transport)
    return agent


def _spans_by_name(exporter: InMemorySpanExporter) -> dict[str, Any]:
    return {s.name: s for s in exporter.get_finished_spans()}


# ---------------------------------------------------------------------------
# Tool span creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_get_workflow_state_creates_span(otel_provider) -> None:
    """get_workflow_state tool creates a span with workflow_id attribute."""
    temporal_client = FakeTemporalClient()
    temporal_client.handles["wf-1"] = FakeWorkflowHandle(
        id="wf-1",
        query_responses={"awaiting": None, "transcript": []},
    )
    agent = _make_agent(temporal_client)

    await agent.call_tool("get_workflow_state", workflow_id="wf-1")

    spans = _spans_by_name(otel_provider)
    assert "tool.get_workflow_state" in spans
    span = spans["tool.get_workflow_state"]
    assert span.attributes["workflow_id"] == "wf-1"


@pytest.mark.asyncio
async def test_tool_submit_input_creates_span(otel_provider) -> None:
    """submit_input tool creates a span with workflow_id and token attributes."""
    temporal_client = FakeTemporalClient()
    temporal_client.handles["wf-1"] = FakeWorkflowHandle(
        id="wf-1",
        query_responses={"awaiting": None, "transcript": []},
    )
    agent = _make_agent(temporal_client)

    await agent.call_tool(
        "submit_input", workflow_id="wf-1", token="tkn_1", value="hello"
    )

    spans = _spans_by_name(otel_provider)
    assert "tool.submit_input" in spans
    span = spans["tool.submit_input"]
    assert span.attributes["workflow_id"] == "wf-1"
    assert span.attributes["token"] == "tkn_1"


@pytest.mark.asyncio
async def test_tool_start_workflow_creates_span(otel_provider) -> None:
    """start_workflow tool creates a span with workflow_id attribute."""
    temporal_client = FakeTemporalClient()
    definition = {
        "schema": "sfsm/0.2",
        "id": "dvla.change_of_address",
        "version": "0.2.0",
        "entry": "main",
        "executor": {},
        "processes": {},
    }
    agent = _make_agent(
        temporal_client,
        http_handler=lambda r: httpx.Response(200, json=definition),
    )

    await agent.call_tool("start_workflow", workflow_id=1)

    spans = _spans_by_name(otel_provider)
    assert "tool.start_workflow" in spans
    span = spans["tool.start_workflow"]
    assert span.attributes["workflow_id"] == 1


@pytest.mark.asyncio
async def test_tool_list_active_workflows_creates_span(otel_provider) -> None:
    """list_active_workflows tool creates a span."""

    class ListableTemporalClient(FakeTemporalClient):
        async def list_workflows(self, query: str):
            return
            yield  # noqa: makes this an async generator

    agent = _make_agent(ListableTemporalClient())
    await agent.call_tool("list_active_workflows")

    spans = _spans_by_name(otel_provider)
    assert "tool.list_active_workflows" in spans


# ---------------------------------------------------------------------------
# Parent-child relationships
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_spans_are_children_of_manual_parent(otel_provider) -> None:
    """Tool spans created within a parent span have the correct parent_span_id."""
    temporal_client = FakeTemporalClient()
    temporal_client.handles["wf-1"] = FakeWorkflowHandle(
        id="wf-1",
        query_responses={"awaiting": None, "transcript": []},
    )
    agent = _make_agent(temporal_client)
    tracer = trace.get_tracer("test")

    with tracer.start_as_current_span("simulated_parent"):
        await agent.call_tool("get_workflow_state", workflow_id="wf-1")

    spans = _spans_by_name(otel_provider)
    parent_span = spans["simulated_parent"]
    tool_span = spans["tool.get_workflow_state"]
    assert tool_span.parent.span_id == parent_span.context.span_id
    assert tool_span.context.trace_id == parent_span.context.trace_id


# ---------------------------------------------------------------------------
# SessionSpanProcessor
# ---------------------------------------------------------------------------


def test_session_processor_stamps_session_id(otel_provider) -> None:
    """SessionSpanProcessor stamps session_id on all spans when set."""
    processor = SessionSpanProcessor()
    _provider.add_span_processor(processor)

    processor.set_session_id("sess-abc-123")
    tracer = trace.get_tracer("test")

    with tracer.start_as_current_span("test_span"):
        pass

    spans = _spans_by_name(otel_provider)
    assert "test_span" in spans
    assert spans["test_span"].attributes["session_id"] == "sess-abc-123"

    processor.set_session_id(None)


# ---------------------------------------------------------------------------
# Activity span enrichment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_http_call_enriches_span_outside_activity_context(
    otel_provider, monkeypatch
) -> None:
    """http_call enriches the current span without crashing outside activity context."""
    monkeypatch.setenv("DVLA_BASE", "http://localhost:9999")

    params = CallParams(
        method="GET",
        url="/test",
        service="dvla",
        headers=None,
        body=None,
        capture={},
        idempotency_key="key-42",
    )

    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("activity_wrapper"):
        try:
            await http_call(params)
        except Exception:
            pass

    spans = _spans_by_name(otel_provider)
    span = spans["activity_wrapper"]
    assert span.attributes["service"] == "dvla"
    assert span.attributes["http.method"] == "GET"
    assert span.attributes["http.url"] == "/test"
    assert span.attributes["idempotency_key"] == "key-42"
    assert "workflow_id" not in span.attributes
