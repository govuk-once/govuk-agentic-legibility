"""Tests for the browser-facing journey executor API adapter."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from starlette.routing import Route

from agents.src.interaction_assistant import (
    AssistanceAction,
    AssistanceRequest,
    ConversationMessage,
)
from agents.src.workflow_executor.api import JourneyRunService, create_app
from agents.src.workflow_executor.client import HttpExchange, HttpExchangeObserver
from agents.src.workflow_executor.protocol import JourneyProtocolDefinition


def api_protocol() -> JourneyProtocolDefinition:
    """Return the protocol used by API adapter tests."""
    return JourneyProtocolDefinition(
        version="2.0",
        next_action_field="next_action",
        terminal_when_absent=True,
        continuation_token_response_field="continuation_token",
        continuation_token_request_field="continuation_token",
        terminal_statuses=frozenset({"completed"}),
        non_terminal_statuses=frozenset({"in_progress"}),
    )


def interaction_response() -> dict[str, Any]:
    """Return one valid non-terminal response."""
    return {
        "status": "in_progress",
        "continuation_token": "secret-token",
        "interaction": {
            "id": "choose_address_entry_method",
            "content": {"title": "Choose how to enter your address"},
            "input_schema": {
                "type": "object",
                "properties": {
                    "use_postcode_lookup": {"type": "boolean"},
                },
                "required": ["use_postcode_lookup"],
            },
        },
        "next_action": {"method": "POST", "path": "/next"},
    }


class FakeClient:
    """Return predetermined journey responses and emit raw exchanges."""

    def __init__(
        self,
        responses: list[dict[str, Any]],
        observer: HttpExchangeObserver | None,
    ) -> None:
        self.responses = responses
        self.observer = observer
        self.results: list[dict[str, Any]] = []

    def get_protocol(self) -> JourneyProtocolDefinition:
        """Return the test protocol."""
        return api_protocol()

    def start_journey(self, journey_id: str) -> dict[str, Any]:
        """Return and trace the first response."""
        return self._respond(f"/journeys/{journey_id}", None)

    def call_action(
        self,
        action: Mapping[str, Any],
        continuation_token: str,
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Record the result and return the next response."""
        self.results.append(dict(result))
        return self._respond(
            str(action["path"]),
            {"continuation_token": "[redacted]", "result": dict(result)},
        )

    def _respond(self, path: str, body: object | None) -> dict[str, Any]:
        response = self.responses.pop(0)
        if self.observer is not None:
            self.observer(
                HttpExchange(
                    method="POST",
                    path=path,
                    request_body=body,
                    status_code=200,
                    response_body=response,
                    duration_ms=1.0,
                )
            )
        return response


class FakeClientFactory:
    """Create one fake client per process-local run."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.clients: list[FakeClient] = []

    def __call__(self, observer: HttpExchangeObserver | None) -> FakeClient:
        """Return a client with its own copy of the response sequence."""
        client = FakeClient(self.responses.copy(), observer)
        self.clients.append(client)
        return client


class FakeAssistant:
    """Return one configured structured proposal without calling a model."""

    model_id = "test-model"
    prompt_id = "test-prompt-v1"

    def __init__(self, action: AssistanceAction) -> None:
        self.action = action
        self.requests: list[AssistanceRequest] = []

    def assist(self, request: AssistanceRequest) -> AssistanceAction:
        """Record the assistant request and return the configured action."""
        self.requests.append(request)
        return self.action


def test_service_completes_a_run_and_exposes_its_trace(tmp_path: Path) -> None:
    """The frontend drives a run without handling continuation fields."""
    factory = FakeClientFactory(
        [interaction_response(), {"status": "completed"}]
    )
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=factory,
    )

    started = service.start("change-driving-licence-address")
    completed = service.submit(started.run_id, {"use_postcode_lookup": True})

    assert started.interaction is not None
    assert started.interaction["id"] == "choose_address_entry_method"
    assert completed.terminal
    assert completed.interaction is None
    assert factory.clients[0].results == [{"use_postcode_lookup": True}]
    assert [event["type"] for event in service.trace_events(started.run_id)] == [
        "run_started",
        "http_exchange",
        "result_submitted",
        "http_exchange",
        "run_finished",
    ]


def test_agent_proposal_does_not_advance_until_reviewed_result_is_submitted(
    tmp_path: Path,
) -> None:
    """Assistance proposes values while the executor remains on the current step."""
    factory = FakeClientFactory([interaction_response(), {"status": "completed"}])
    assistant = FakeAssistant(
        AssistanceAction(
            type="propose_values",
            values={"use_postcode_lookup": True},
        )
    )
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=factory,
        assistant=assistant,
    )

    started = service.start("change-driving-licence-address")
    assistance = service.assist(
        started.run_id,
        message="Yes, use my postcode",
        conversation=[
            ConversationMessage(role="user", content="I need to change my address")
        ],
    )

    assert assistance.action.values == {"use_postcode_lookup": True}
    assert factory.clients[0].results == []
    assert assistant.requests[0].interaction["id"] == "choose_address_entry_method"

    completed = service.submit(started.run_id, {"use_postcode_lookup": True})

    assert completed.terminal
    events = service.trace_events(started.run_id)
    assert [event["type"] for event in events] == [
        "run_started",
        "http_exchange",
        "user_message",
        "agent_invoked",
        "agent_responded",
        "proposal_reviewed",
        "result_submitted",
        "http_exchange",
        "run_finished",
    ]
    reviewed = events[5]
    assert reviewed["changed"] is False
    assert reviewed["changed_fields"] == []


def test_unconfigured_assistance_is_traced_without_advancing_run(
    tmp_path: Path,
) -> None:
    """Manual execution remains available when no model has been configured."""
    factory = FakeClientFactory([interaction_response()])
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=factory,
    )
    started = service.start("change-driving-licence-address")

    with pytest.raises(RuntimeError, match="not configured"):
        service.assist(started.run_id, message="Use my postcode", conversation=[])

    assert factory.clients[0].results == []
    assert [event["type"] for event in service.trace_events(started.run_id)] == [
        "run_started",
        "http_exchange",
        "user_message",
        "agent_failed",
    ]


def test_service_rejects_missing_and_completed_runs(tmp_path: Path) -> None:
    """Process-local runs cannot be addressed after loss or completion."""
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=FakeClientFactory([{"status": "completed"}]),
    )

    with pytest.raises(KeyError):
        service.trace_events("missing")

    completed = service.start("already-complete")
    with pytest.raises(RuntimeError):
        service.submit(completed.run_id, {"answer": True})


def test_app_exposes_generic_run_routes(tmp_path: Path) -> None:
    """The HTTP adapter does not expose journey-specific endpoint paths."""
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=FakeClientFactory([interaction_response()]),
    )

    paths = {
        route.path
        for route in create_app(run_service=service).routes
        if isinstance(route, Route)
    }

    assert {
        "/healthcheck",
        "/api/journey-runs",
        "/api/journey-runs/{run_id}/assistance",
        "/api/journey-runs/{run_id}/results",
        "/api/journey-runs/{run_id}/trace",
    }.issubset(paths)
