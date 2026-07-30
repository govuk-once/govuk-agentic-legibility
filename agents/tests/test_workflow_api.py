"""Tests for the browser-facing journey executor API adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from starlette.routing import Route

from agents.src.evaluation import ConversationFixtureRepository
from agents.src.interaction_assistant import (
    AssistanceAction,
    AssistanceContext,
    AssistanceRequest,
    AssistanceResult,
)
from agents.src.workflow_executor.api import JourneyRunService, create_app
from agents.src.workflow_executor.client import HttpExchange, HttpExchangeObserver
from agents.src.workflow_executor.guidance import (
    GuidanceDirectory,
    GuidanceDocument,
    GuidanceReference,
    GuidanceTopic,
)
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

    def list_guidance(self, journey_id: str) -> GuidanceDirectory:
        """Return and trace compact guidance metadata."""
        directory = GuidanceDirectory(
            version="1",
            topics=[
                GuidanceTopic(
                    id="postcode-lookup-for-flats",
                    title="Using postcode lookup for a flat",
                    description="Use for questions about flats and postcode lookup.",
                )
            ],
        )
        self._emit_guidance_exchange(
            f"/journeys/{journey_id}/guidance",
            directory.model_dump(mode="json"),
        )
        return directory

    def get_guidance(
        self,
        journey_id: str,
        topic_id: str,
    ) -> GuidanceDocument:
        """Return and trace one Markdown guidance document."""
        document = GuidanceDocument(
            id=topic_id,
            title="Using postcode lookup for a flat",
            description="Use for questions about flats and postcode lookup.",
            version="1",
            content_type="text/markdown",
            content="# Flats\n\nYou can use postcode lookup for a flat.",
            sha256="a" * 64,
        )
        self._emit_guidance_exchange(
            f"/journeys/{journey_id}/guidance/{topic_id}",
            document.model_dump(mode="json"),
        )
        return document

    def _emit_guidance_exchange(
        self,
        path: str,
        response_body: dict[str, object],
    ) -> None:
        if self.observer is not None:
            self.observer(
                HttpExchange(
                    method="GET",
                    path=path,
                    request_body=None,
                    status_code=200,
                    response_body=response_body,
                    duration_ms=1.0,
                )
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
    """Return configured structured actions without calling a model."""

    model_id = "test-model"
    prompt_id = "test-prompt-v4"

    def __init__(self, actions: list[AssistanceAction]) -> None:
        self.actions = actions
        self.requests: list[AssistanceRequest] = []

    def assist(
        self,
        request: AssistanceRequest,
        context: AssistanceContext,
    ) -> AssistanceResult:
        """Record the assistant request and return the next configured action."""
        del context
        self.requests.append(request)
        return AssistanceResult(action=self.actions.pop(0))


class GuidanceUsingAssistant:
    """Exercise the run-scoped guidance tools without a model."""

    model_id = "test-model"
    prompt_id = "test-prompt-v4"

    def assist(
        self,
        request: AssistanceRequest,
        context: AssistanceContext,
    ) -> AssistanceResult:
        """List and retrieve guidance, recording each selected tool call."""
        del request
        list_arguments: dict[str, object] = {}
        context.tool_recorder.record_agent_tool_requested(
            tool="list_journey_guidance",
            arguments=list_arguments,
        )
        directory = context.guidance.list_guidance(context.journey_id)
        context.tool_recorder.record_agent_tool_completed(
            tool="list_journey_guidance",
            arguments=list_arguments,
            result=directory.model_dump(mode="json"),
        )

        topic_id = directory.topics[0].id
        get_arguments = {"topic_id": topic_id}
        context.tool_recorder.record_agent_tool_requested(
            tool="get_journey_guidance",
            arguments=get_arguments,
        )
        document = context.guidance.get_guidance(context.journey_id, topic_id)
        reference = GuidanceReference.from_document(document)
        context.tool_recorder.record_agent_tool_completed(
            tool="get_journey_guidance",
            arguments=get_arguments,
            result=reference.model_dump(mode="json"),
        )
        return AssistanceResult(
            action=AssistanceAction(
                type="answer_journey_question",
                answer="You can use postcode lookup if you live in a flat.",
            ),
            retrieved_guidance=[reference],
        )


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


def test_noagent_web_run_never_invokes_assistant(tmp_path: Path) -> None:
    """A no-agent web consumer uses the same service without agent assistance."""
    factory = FakeClientFactory(
        [
            interaction_response(),
            interaction_response("find_address_by_postcode"),
        ]
    )
    assistant = FakeAssistant(
        [
            AssistanceAction(
                type="propose_values",
                values={"use_postcode_lookup": True},
            )
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
        assistance_enabled=False,
        consumer="noagent_web_frontend",
    )
    second = service.submit(started.run_id, {"use_postcode_lookup": True})

    assert started.assistance is None
    assert second.assistance is None
    assert assistant.requests == []
    events = service.trace_events(started.run_id)
    assert events[0]["consumer"] == "noagent_web_frontend"
    assert "agent_invoked" not in [event["type"] for event in events]


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
    assert [request.trigger.type for request in assistant.requests] == [
        "interaction_opened",
        "interaction_opened",
    ]
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
    assert assistant.requests[-1].trigger.type == "user_message_added"
    assert assistant.requests[-1].trigger.message == "Actually, enter it manually."


def test_journey_answer_without_guidance_is_recorded_not_rejected(
    tmp_path: Path,
) -> None:
    """Ungrounded model behaviour remains a complete, scoreable run outcome."""
    assistant = FakeAssistant(
        [
            AssistanceAction(
                type="answer_journey_question",
                answer="You can use postcode lookup if you live in a flat.",
            )
        ]
    )
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=FakeClientFactory([interaction_response()]),
        assistant=assistant,
        fixture_repository=fixture_repository(tmp_path),
    )
    started = service.start("change-driving-licence-address")

    answered = service.add_message(
        started.run_id,
        "Should I use postcode lookup if I live in a flat?",
    )

    assert answered.interaction == started.interaction
    assert answered.assistance is not None
    assert answered.assistance.action.type == "answer_journey_question"
    assert answered.assistance.retrieved_guidance == []
    assert answered.conversation[-1].role == "assistant"
    assert assistant.requests[-1].trigger.type == "user_message_added"
    events = service.trace_events(started.run_id)
    presented = next(event for event in events if event["type"] == "answer_presented")
    assert presented["grounded_in_retrieved_guidance"] is False
    assert "agent_failed" not in [event["type"] for event in events]


def test_next_interaction_does_not_repeat_an_earlier_journey_answer(
    tmp_path: Path,
) -> None:
    """After progression, the assistant is told to support the newly opened form."""
    assistant = FakeAssistant(
        [
            AssistanceAction(
                type="answer_journey_question",
                answer="You can use postcode lookup if you live in a flat.",
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
        client_factory=FakeClientFactory(
            [
                interaction_response(),
                interaction_response("find_address_by_postcode"),
            ]
        ),
        assistant=assistant,
        fixture_repository=fixture_repository(tmp_path),
    )
    started = service.start("change-driving-licence-address")
    answered = service.add_message(
        started.run_id,
        "Should I use postcode lookup if I live in a flat?",
    )
    next_interaction = service.submit(
        started.run_id,
        {"use_postcode_lookup": True},
    )

    assert answered.assistance is not None
    assert answered.assistance.action.type == "answer_journey_question"
    assert next_interaction.assistance is not None
    assert next_interaction.assistance.action.type == "propose_values"
    assert [request.trigger.type for request in assistant.requests] == [
        "user_message_added",
        "interaction_opened",
    ]



def test_journey_answer_records_tool_http_and_guidance_evidence(tmp_path: Path) -> None:
    """A grounded answer records model tool selection and service retrievals."""
    service = JourneyRunService(
        trace_directory=tmp_path,
        client_factory=FakeClientFactory([interaction_response()]),
        assistant=GuidanceUsingAssistant(),
        fixture_repository=fixture_repository(tmp_path),
    )
    started = service.start("change-driving-licence-address")

    answered = service.add_message(
        started.run_id,
        "Should I use postcode lookup if I live in a flat?",
    )

    assert answered.assistance is not None
    assert [item.id for item in answered.assistance.retrieved_guidance] == [
        "postcode-lookup-for-flats"
    ]
    event_types = [event["type"] for event in service.trace_events(started.run_id)]
    assert event_types == [
        "run_started",
        "http_exchange",
        "user_message",
        "agent_invoked",
        "agent_tool_requested",
        "http_exchange",
        "agent_tool_completed",
        "agent_tool_requested",
        "http_exchange",
        "agent_tool_completed",
        "agent_responded",
        "answer_presented",
    ]
    presented = service.trace_events(started.run_id)[-1]
    assert presented["grounded_in_retrieved_guidance"] is True


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
