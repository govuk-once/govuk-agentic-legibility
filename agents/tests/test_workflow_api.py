"""Tests for the browser-facing journey executor API adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from starlette.routing import Route

from agents.src.evaluation import ConversationFixtureRepository
from agents.src.interaction_assistant import AssistanceAction, AssistanceRequest
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


def interaction_response(
    interaction_id: str = "choose_address_entry_method",
) -> dict[str, Any]:
    """Return one valid non-terminal response.

    Args:
        interaction_id: Interaction identifier and schema variant to return.

    Returns:
        Valid server-driven journey response.
    """
    properties: dict[str, object]
    if interaction_id == "choose_address_entry_method":
        properties = {"use_postcode_lookup": {"type": "boolean"}}
    else:
        properties = {
            "postcode": {"type": "string"},
            "building_number_or_name": {"type": "string"},
        }
    return {
        "status": "in_progress",
        "continuation_token": f"token-{interaction_id}",
        "interaction": {
            "id": interaction_id,
            "content": {"title": interaction_id},
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
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
    """Return configured structured proposals without calling a model."""

    model_id = "test-model"
    prompt_id = "test-prompt-v2"

    def __init__(self, actions: list[AssistanceAction]) -> None:
        self.actions = actions
        self.requests: list[AssistanceRequest] = []

    def assist(self, request: AssistanceRequest) -> AssistanceAction:
        """Record the assistant request and return the next configured action."""
        self.requests.append(request)
        return self.actions.pop(0)


def fixture_repository(tmp_path: Path) -> ConversationFixtureRepository:
    """Write and return one fixed conversation fixture repository.

    Args:
        tmp_path: Temporary directory supplied by pytest.

    Returns:
        Repository containing one address fixture.
    """
    fixture_directory = tmp_path / "fixtures"
    fixture_directory.mkdir()
    (fixture_directory / "address.json").write_text(
        json.dumps(
            {
                "id": "address-context",
                "version": "1",
                "title": "Address context",
                "description": "A complete address and lookup preference",
                "journey_id": "change-driving-licence-address",
                "conversation": [
                    {
                        "role": "user",
                        "content": (
                            "My address is 18 Station Road, BS1 3AB. "
                            "Use postcode lookup."
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return ConversationFixtureRepository(fixture_directory)


def test_service_completes_manual_run_and_exposes_trace(tmp_path: Path) -> None:
    """A run without conversation context remains manually executable."""
    factory = FakeClientFactory([interaction_response(), {"status": "completed"}])
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=factory,
        fixture_repository=fixture_repository(tmp_path),
    )

    started = service.start("change-driving-licence-address")
    completed = service.submit(started.run_id, {"use_postcode_lookup": True})

    assert started.assistance is None
    assert started.conversation == []
    assert completed.terminal
    assert factory.clients[0].results == [{"use_postcode_lookup": True}]


def test_fixture_generates_default_proposals_at_each_interaction(
    tmp_path: Path,
) -> None:
    """The complete fixed conversation is reused automatically at every step."""
    factory = FakeClientFactory(
        [
            interaction_response(),
            interaction_response("find_address_by_postcode"),
            {"status": "completed"},
        ]
    )
    assistant = FakeAssistant(
        [
            AssistanceAction(
                type="propose_values",
                values={"use_postcode_lookup": True},
            ),
            AssistanceAction(
                type="propose_values",
                values={
                    "postcode": "BS1 3AB",
                    "building_number_or_name": "18",
                },
            ),
        ]
    )
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=factory,
        assistant=assistant,
        fixture_repository=fixture_repository(tmp_path),
    )

    started = service.start(
        "change-driving-licence-address",
        fixture_id="address-context",
        consumer="automated_fixture",
    )
    second = service.submit(started.run_id, {"use_postcode_lookup": True})

    assert started.assistance is not None
    assert started.assistance.action.values == {"use_postcode_lookup": True}
    assert second.assistance is not None
    assert second.assistance.action.values["postcode"] == "BS1 3AB"
    assert len(assistant.requests) == 2
    assert assistant.requests[0].conversation == assistant.requests[1].conversation
    events = service.trace_events(started.run_id)
    assert events[0]["consumer"] == "automated_fixture"
    assert [event["type"] for event in events] == [
        "run_started",
        "fixture_loaded",
        "http_exchange",
        "agent_invoked",
        "agent_responded",
        "proposal_reviewed",
        "result_submitted",
        "http_exchange",
        "agent_invoked",
        "agent_responded",
    ]


def test_new_message_extends_context_without_adding_agent_proposal(
    tmp_path: Path,
) -> None:
    """Journey clarifications are conversation; agent outputs remain trace events."""
    assistant = FakeAssistant(
        [
            AssistanceAction(type="no_safe_suggestion", message="Need a preference."),
            AssistanceAction(
                type="propose_values",
                values={"use_postcode_lookup": False},
            ),
        ]
    )
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=FakeClientFactory([interaction_response()]),
        assistant=assistant,
        fixture_repository=fixture_repository(tmp_path),
    )
    started = service.start(
        "change-driving-licence-address",
        fixture_id="address-context",
    )

    updated = service.add_message(started.run_id, "Actually, enter it manually.")

    assert [message.content for message in updated.conversation] == [
        "My address is 18 Station Road, BS1 3AB. Use postcode lookup.",
        "Actually, enter it manually.",
    ]
    assert updated.assistance is not None
    assert updated.assistance.action.values == {"use_postcode_lookup": False}
    assert len(assistant.requests[-1].conversation) == 2


def test_unconfigured_fixture_run_stays_manually_usable(tmp_path: Path) -> None:
    """Missing model configuration is exposed without preventing journey execution."""
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=FakeClientFactory([interaction_response()]),
        fixture_repository=fixture_repository(tmp_path),
    )

    started = service.start(
        "change-driving-licence-address",
        fixture_id="address-context",
    )

    assert started.assistance is None
    assert started.assistance_error == "Interaction assistant is not configured"
    assert service.trace_events(started.run_id)[-1]["type"] == "agent_failed"


def test_service_rejects_missing_and_completed_runs(tmp_path: Path) -> None:
    """Process-local runs cannot be addressed after loss or completion."""
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=FakeClientFactory([{"status": "completed"}]),
        fixture_repository=fixture_repository(tmp_path),
    )

    with pytest.raises(KeyError):
        service.trace_events("missing")

    completed = service.start("already-complete")
    with pytest.raises(RuntimeError):
        service.submit(completed.run_id, {"answer": True})


def test_app_exposes_generic_fixture_and_run_routes(tmp_path: Path) -> None:
    """The HTTP adapter exposes inputs and operations without journey-specific paths."""
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=FakeClientFactory([interaction_response()]),
        fixture_repository=fixture_repository(tmp_path),
    )

    paths = {
        route.path
        for route in create_app(run_service=service).routes
        if isinstance(route, Route)
    }

    assert {
        "/healthcheck",
        "/api/conversation-fixtures",
        "/api/journey-runs",
        "/api/journey-runs/{run_id}/messages",
        "/api/journey-runs/{run_id}/results",
        "/api/journey-runs/{run_id}/trace",
    }.issubset(paths)
