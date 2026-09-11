"""Tests for the Strands agent composition layer and value coercion logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from agent.agent import (
    WorkflowAgent,
    _coerce_value,
    build_contextual_prompt,
)


# ---------------------------------------------------------------------------
# Fakes
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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _state_with_schema(kind: str, **extra: Any) -> dict[str, Any]:
    schema = {"kind": kind, **extra}
    return {
        "workflow_id": "sfsm-test-12345",
        "awaiting": {"token": "tkn_1", "prompt": "?", "schema": schema},
    }


# ---------------------------------------------------------------------------
# Coercion Tests
# ---------------------------------------------------------------------------


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


# --- file_ref Coercion ---


def test_coerce_file_ref_from_ui_upload_string() -> None:
    """Coerces [Uploaded File: ...] formatted string into a valid file dictionary."""
    val = "[Uploaded File: ref='certificate.pdf', content_type='application/pdf', bytes=2048]"
    state = _state_with_schema("file_ref")
    result = _coerce_value(val, state)

    assert isinstance(result, dict)
    assert result["ref"] == "certificate.pdf"
    assert result["content_type"] == "application/pdf"
    assert result["bytes"] == 2048


def test_coerce_file_ref_from_json_string_passed_by_llm() -> None:
    """Coerces stringified JSON payload passed by LLM into a valid file dictionary."""
    val = '{"ref": "pic.jpeg", "content_type": "image/jpeg", "bytes": 20222}'
    state = _state_with_schema("file_ref")
    result = _coerce_value(val, state)

    assert isinstance(result, dict)
    assert result["ref"] == "pic.jpeg"
    assert result["content_type"] == "image/jpeg"
    assert result["bytes"] == 20222


def test_coerce_file_ref_dict_missing_ref_generates_fallback() -> None:
    """Populates fallback ref key when LLM passes dictionary without ref."""
    val = {"content_type": "image/jpeg", "bytes": 5000}
    state = _state_with_schema("file_ref")
    result = _coerce_value(val, state)

    assert isinstance(result, dict)
    assert result["ref"] == "upload_sfsm-test-12345.dat"
    assert result["content_type"] == "image/jpeg"
    assert result["bytes"] == 5000


def test_coerce_file_ref_plain_text_rejected() -> None:
    """Rejects arbitrary user text input (e.g. 'pic') with invalid error payload."""
    val = "pic"
    state = _state_with_schema("file_ref")
    result = _coerce_value(val, state)

    assert result == {"error": "INVALID_FILE_UPLOAD"}


# --- select_one Coercion ---


def test_coerce_select_one_matching_value_key() -> None:
    """Coerces exact string value key for select_one schema."""
    options = [
        {
            "value": "pregnancy_sick_leave",
            "label": "Off work with pregnancy-related illness",
        },
        {
            "value": "not_stopped_working",
            "label": "Still working / have not stopped yet",
        },
    ]
    state = _state_with_schema("select_one", options=options)
    result = _coerce_value("not_stopped_working", state)

    assert result == "not_stopped_working"


def test_coerce_select_one_matching_label_text() -> None:
    """Coerces natural language label text back to its target value key."""
    options = [
        {
            "value": "pregnancy_sick_leave",
            "label": "Off work with pregnancy-related illness",
        },
        {
            "value": "not_stopped_working",
            "label": "Still working / have not stopped yet",
        },
    ]
    state = _state_with_schema("select_one", options=options)
    result = _coerce_value("Still working / have not stopped yet", state)

    assert result == "not_stopped_working"


# --- select_many Coercion ---


def test_coerce_select_many_from_json_array_string() -> None:
    """Parses JSON array string into native Python list."""
    val = '["employed", "self_employed"]'
    state = _state_with_schema("select_many")
    result = _coerce_value(val, state)

    assert result == ["employed", "self_employed"]


def test_coerce_select_many_from_comma_separated_string() -> None:
    """Splits comma-separated natural text choices into native list."""
    val = "employed, self_employed"
    state = _state_with_schema("select_many")
    result = _coerce_value(val, state)

    assert result == ["employed", "self_employed"]


def test_coerce_no_state_returns_unchanged() -> None:
    assert _coerce_value("Yes", None) == "Yes"


def test_coerce_no_awaiting_returns_unchanged() -> None:
    state = {"workflow_id": "wf-1", "awaiting": None}
    assert _coerce_value("Yes", state) == "Yes"


# ---------------------------------------------------------------------------
# Contextual Prompt Building
# ---------------------------------------------------------------------------


def test_build_contextual_prompt_without_state() -> None:
    result = build_contextual_prompt("Hello", context=None)
    assert result == "Hello"


def test_build_contextual_prompt_with_awaiting_state() -> None:
    context = {
        "workflow_id": "sfsm-dvla.change_of_address-0.2.0",
        "awaiting": {
            "token": "tkn_3",
            "prompt": "Please enter your new postcode.",
            "schema": {
                "kind": "string",
                "pattern": "[A-Z]{1,2}\\d[A-Z\\d]?\\s*\\d[A-Z]{2}",
            },
        },
    }
    result = build_contextual_prompt("SW1A 2AA", context=context)

    assert "sfsm-dvla.change_of_address-0.2.0" in result
    assert "tkn_3" in result
    assert "Please enter your new postcode." in result
    assert "SW1A 2AA" in result


# ---------------------------------------------------------------------------
# WorkflowAgent Integration Tests
# ---------------------------------------------------------------------------


def make_test_agent(
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


def test_agent_exposes_expected_tool_names() -> None:
    agent = make_test_agent(FakeTemporalClient())

    tool_names = agent.tool_names()
    assert "get_workflow_definition" in tool_names
    assert "start_workflow" in tool_names
    assert "get_workflow_state" in tool_names
    assert "submit_input" in tool_names
    assert "list_active_workflows" in tool_names
    assert "find_workflow_by_intent" in tool_names


@pytest.mark.asyncio
async def test_get_workflow_state_tool_returns_instruction_when_not_awaiting() -> None:
    temporal_client = FakeTemporalClient()
    handle = FakeWorkflowHandle(
        id="wf-1",
        execution_status="RUNNING",
        query_responses={
            "awaiting": None,
            "transcript": [],
        },
    )
    temporal_client.handles["wf-1"] = handle

    agent = make_test_agent(temporal_client)

    result = await agent.call_tool("get_workflow_state", workflow_id="wf-1")
    assert result["awaiting"] is None
    assert "message" in result
    assert "Do not re-query" in result["message"] or "instructed" in result["message"]
