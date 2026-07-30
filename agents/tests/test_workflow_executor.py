"""Tests for the generic server-driven journey executor."""

from __future__ import annotations

import io
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

import agents.src.workflow_executor.config as workflow_executor_config
from agents.src.workflow_executor.client import HttpExchange, JourneyClient
from agents.src.workflow_executor.config import (
    load_executor_environment,
    resolve_base_url,
)
from agents.src.workflow_executor.errors import (
    JourneyConfigurationError,
    JourneyHttpError,
    JourneyProtocolError,
)
from agents.src.workflow_executor.executor import JourneyExecutor
from agents.src.workflow_executor.protocol import JourneyProtocolDefinition
from agents.src.workflow_executor.input_provider import JsonCliInputProvider
from agents.src.workflow_executor.state import load_response, save_response


def executor_protocol() -> JourneyProtocolDefinition:
    """Return the catalogue rules used by executor unit tests."""
    return JourneyProtocolDefinition(
        version="2.0",
        next_action_field="next_action",
        terminal_when_absent=True,
        continuation_token_response_field="continuation_token",
        continuation_token_request_field="continuation_token",
        terminal_statuses=frozenset(
            {
                "another_terminal_name",
                "completed",
                "confirmation_declined",
                "done",
                "finished",
            }
        ),
        non_terminal_statuses=frozenset(
            {
                "anything",
                "first_unknown_status",
                "in_progress",
                "ready_for_confirmation",
                "second_unknown_status",
                "still_waiting",
                "waiting",
            }
        ),
    )


def catalogue_response() -> dict[str, Any]:
    """Return a complete protocol catalogue for HTTP client tests."""
    protocol = executor_protocol()
    return {
        "protocol": {
            "version": protocol.version,
            "terminality": {
                "next_action_field": protocol.next_action_field,
                "terminal_when_absent": protocol.terminal_when_absent,
            },
            "continuation_token": {
                "response_field": protocol.continuation_token_response_field,
                "request_field": protocol.continuation_token_request_field,
            },
            "statuses": [
                *[
                    {"value": value, "terminal": False}
                    for value in sorted(protocol.non_terminal_statuses)
                ],
                *[
                    {"value": value, "terminal": True}
                    for value in sorted(protocol.terminal_statuses)
                ],
            ],
        },
        "journeys": [],
    }


class FakeResponse:
    """Minimal requests response used by the HTTP client tests."""

    def __init__(
        self,
        payload: object,
        *,
        status_code: int = 200,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self) -> object:
        """Return the configured response payload."""
        return self._payload

    def raise_for_status(self) -> None:
        """Raise an HTTP error for non-successful responses."""
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self  # type: ignore[assignment]
            raise error


class FakeSession:
    """Record HTTP calls and return queued responses."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        """Record a request and return the next queued response."""
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


class FakeJourneyClient:
    """Journey client that returns predetermined protocol responses."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.started_journey: str | None = None
        self.action_calls: list[dict[str, Any]] = []

    def get_protocol(self) -> JourneyProtocolDefinition:
        """Return the protocol advertised to the executor tests."""
        return executor_protocol()

    def start_journey(self, journey_id: str) -> dict[str, Any]:
        """Record the journey and return the first response."""
        self.started_journey = journey_id
        return self.responses.pop(0)

    def call_action(
        self,
        action: Mapping[str, Any],
        continuation_token: str,
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Record one action and return the next response."""
        self.action_calls.append(
            {
                "action": dict(action),
                "continuation_token": continuation_token,
                "result": dict(result),
            }
        )
        return self.responses.pop(0)


def non_terminal_response(
    token: str,
    *,
    status: str,
    path: str = "/next",
) -> dict[str, Any]:
    """Build a generic non-terminal response for tests."""
    return {
        "status": status,
        "continuation_token": token,
        "interaction": {
            "content": {"title": f"Interaction for {status}"},
            "input_schema": {"type": "object"},
        },
        "next_action": {"method": "POST", "path": path},
    }


def test_client_uses_catalogue_to_start_advertised_journey() -> None:
    """The start route comes from the catalogue rather than client code."""
    catalogue = catalogue_response()
    catalogue["journeys"] = [
        {
            "id": "change-driving-licence-address",
            "title": "Change driving-licence address",
            "operations": {
                "start": {
                    "method": "POST",
                    "path": "/advertised-start",
                }
            },
        }
    ]
    session = FakeSession(
        [
            FakeResponse(catalogue),
            FakeResponse(non_terminal_response("token-1", status="anything")),
        ]
    )

    client = JourneyClient("http://journey.test", session=session)
    response = client.start_journey("change-driving-licence-address")

    assert response["continuation_token"] == "token-1"
    assert [call["url"] for call in session.calls] == [
        "http://journey.test/app/dvla/v1/journeys",
        "http://journey.test/advertised-start",
    ]


def test_client_submits_generic_result_to_advertised_action() -> None:
    """The client carries the latest token and result to the advertised path."""
    session = FakeSession(
        [FakeResponse(catalogue_response()), FakeResponse({"status": "finished"})]
    )
    client = JourneyClient("http://journey.test", session=session)

    client.call_action(
        {"method": "POST", "path": "/advertised-action"},
        "latest-token",
        {"confirmed": True},
    )

    assert session.calls[1]["json"] == {
        "continuation_token": "latest-token",
        "result": {"confirmed": True},
    }
    assert session.calls[1]["url"] == "http://journey.test/advertised-action"


def test_executor_exposes_stepwise_operations_without_interpreting_status() -> None:
    """Different consumers can advance the journey one response at a time."""
    client = FakeJourneyClient(
        [
            non_terminal_response("token-1", status="first_unknown_status"),
            non_terminal_response("token-2", status="second_unknown_status"),
            {"status": "another_terminal_name", "result": {"ok": True}},
        ]
    )
    executor = JourneyExecutor(client)

    first = executor.start("example-journey")
    assert executor.current_interaction(first) is not None

    second = executor.submit(first, {"first": 1})
    assert executor.current_interaction(second) is not None

    terminal = executor.submit(second, {"second": 2})

    assert terminal == {
        "status": "another_terminal_name",
        "result": {"ok": True},
    }
    assert executor.is_terminal(terminal)
    assert executor.current_interaction(terminal) is None
    assert [call["continuation_token"] for call in client.action_calls] == [
        "token-1",
        "token-2",
    ]
    assert [call["result"] for call in client.action_calls] == [
        {"first": 1},
        {"second": 2},
    ]


def test_executor_can_continue_from_a_response_held_by_another_consumer() -> None:
    """The latest response alone is sufficient for a later submit operation."""
    client = FakeJourneyClient(
        [
            non_terminal_response("token-1", status="waiting"),
            {"status": "done"},
        ]
    )
    executor = JourneyExecutor(client)

    response_held_by_consumer = executor.start("example-journey")
    completed = executor.submit(response_held_by_consumer, {"answer": True})

    assert completed == {"status": "done"}


def test_executor_rejects_submission_to_terminal_response() -> None:
    """Consumers cannot submit another result after the service terminates."""
    executor = JourneyExecutor(FakeJourneyClient([]))

    with pytest.raises(JourneyProtocolError, match="terminal journey response"):
        executor.submit({"status": "done"}, {"answer": True})


def test_executor_validates_each_non_terminal_response() -> None:
    """Consumers receive an error rather than an unusable protocol response."""
    client = FakeJourneyClient(
        [
            {
                "status": "waiting",
                "interaction": {"content": {}},
                "next_action": {"method": "POST", "path": "/next"},
            }
        ]
    )

    with pytest.raises(JourneyProtocolError, match="continuation_token"):
        JourneyExecutor(client).start("example-journey")


def test_state_file_round_trip(tmp_path: Path) -> None:
    """The complete latest response can be persisted and loaded."""
    response = non_terminal_response("token-1", status="waiting")
    state_file = tmp_path / "journey-state.json"

    save_response(response, state_file)

    assert load_response(state_file) == response


def test_json_cli_provider_retries_until_object_is_entered() -> None:
    """The developer CLI rejects malformed JSON and non-object results."""
    answers = iter(["not json", "[1, 2]", '{"answer": true}'])
    output = io.StringIO()
    provider = JsonCliInputProvider(
        input_function=lambda _prompt: next(answers),
        output=output,
    )

    result = provider.collect(
        {
            "content": {"title": "Question"},
            "input_schema": {"type": "object"},
        }
    )

    assert result == {"answer": True}
    assert "Invalid JSON" in output.getvalue()
    assert "must be a JSON object" in output.getvalue()


def test_client_rejects_unsupported_protocol_version() -> None:
    """The executor fails before starting an unsupported protocol."""
    session = FakeSession(
        [FakeResponse({"protocol": {"version": "99.0"}, "journeys": []})]
    )
    client = JourneyClient("http://journey.test", session=session)

    with pytest.raises(JourneyProtocolError, match="Unsupported journey protocol"):
        client.get_catalogue()


def test_client_rejects_cross_origin_next_action() -> None:
    """Advertised actions cannot send journey data to another origin."""
    client = JourneyClient("http://journey.test")

    with pytest.raises(JourneyProtocolError, match="configured service origin"):
        client.call_action(
            {"method": "POST", "path": "https://other.test/collect"},
            "token",
            {"value": "secret"},
        )


def test_client_surfaces_service_error_detail() -> None:
    """Non-successful service responses become useful executor errors."""
    session = FakeSession(
        [
            FakeResponse(catalogue_response()),
            FakeResponse({"detail": "Address not found"}, status_code=404),
        ]
    )
    exchanges: list[HttpExchange] = []
    client = JourneyClient(
        "http://journey.test",
        session=session,
        on_exchange=exchanges.append,
    )

    with pytest.raises(JourneyHttpError, match="Address not found"):
        client.call_action(
            {"method": "POST", "path": "/next"},
            "token",
            {"postcode": "SW1A 1AA"},
        )

    failed_exchange = exchanges[-1]
    assert failed_exchange.status_code == 404
    assert failed_exchange.response_body == {"detail": "Address not found"}
    assert failed_exchange.error is not None


def test_load_executor_environment_reads_agents_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The standalone CLI can use the same ``agents/.env`` file as the agents."""
    env_file = tmp_path / ".env"
    env_file.write_text("USE_STUB_SERVER=1\n", encoding="utf-8")
    monkeypatch.delenv("USE_STUB_SERVER", raising=False)
    monkeypatch.setattr(workflow_executor_config, "AGENTS_ENV_FILE", env_file)

    load_executor_environment()

    assert os.environ["USE_STUB_SERVER"] == "1"


def test_resolve_base_url_prefers_explicit_and_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local URLs do not require AWS access."""
    monkeypatch.setenv("STUB_SERVER_URL", "http://environment.test")

    assert resolve_base_url("http://explicit.test") == "http://explicit.test"
    assert resolve_base_url() == "http://environment.test"


def test_resolve_base_url_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing local and deployed-stub configuration is reported clearly."""
    monkeypatch.delenv("STUB_SERVER_URL", raising=False)
    monkeypatch.delenv("USE_STUB_SERVER", raising=False)

    with pytest.raises(JourneyConfigurationError, match="Set --base-url"):
        resolve_base_url()


def test_resolve_base_url_reads_parameter_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deployed stub URL can be discovered using the existing SSM parameter."""
    monkeypatch.delenv("STUB_SERVER_URL", raising=False)
    monkeypatch.setenv("USE_STUB_SERVER", "1")
    ssm = Mock()
    ssm.get_parameter.return_value = {
        "Parameter": {"Value": "https://deployed.example"}
    }
    monkeypatch.setattr(
        "agents.src.workflow_executor.config.boto3.client",
        lambda *_args, **_kwargs: ssm,
    )

    assert resolve_base_url() == "https://deployed.example"


def test_client_traces_exchanges_using_protocol_token_field_names() -> None:
    """Trace observers receive transport evidence with protocol tokens redacted."""
    catalogue = {
        "protocol": {
            "version": "2.0",
            "terminality": {
                "next_action_field": "continue_with",
                "terminal_when_absent": True,
            },
            "continuation_token": {
                "response_field": "cursor",
                "request_field": "cursor_input",
            },
            "statuses": [
                {"value": "waiting", "terminal": False},
                {"value": "done", "terminal": True},
            ],
        },
        "journeys": [
            {
                "id": "example-journey",
                "title": "Example journey",
                "operations": {
                    "start": {"method": "POST", "path": "/start"},
                },
            }
        ],
    }
    first_response = {
        "status": "waiting",
        "cursor": "response-secret",
        "interaction": {
            "id": "question",
            "content": {"title": "Question"},
            "input_schema": {"type": "object"},
        },
        "continue_with": {"method": "POST", "path": "/continue"},
    }
    session = FakeSession(
        [
            FakeResponse(catalogue),
            FakeResponse(first_response),
            FakeResponse({"status": "done"}),
        ]
    )
    exchanges: list[HttpExchange] = []
    client = JourneyClient(
        "http://journey.test",
        session=session,
        on_exchange=exchanges.append,
    )

    response = client.start_journey("example-journey")
    client.call_action(
        response["continue_with"],
        "request-secret",
        {"answer": True},
    )

    assert len(exchanges) == 3
    traced_start_response = exchanges[1].response_body
    assert isinstance(traced_start_response, dict)
    assert traced_start_response["cursor"] == "[redacted]"
    assert exchanges[2].request_body == {
        "cursor_input": "[redacted]",
        "result": {"answer": True},
    }
    assert session.calls[2]["json"]["cursor_input"] == "request-secret"


def test_client_discovers_progressive_guidance_operations_from_catalogue() -> None:
    """Guidance directory and document paths come from the journey contract."""
    session = FakeSession(
        [
            FakeResponse(
                {
                    "protocol": {
                        "version": "2.0",
                        "terminality": {
                            "next_action_field": "next_action",
                            "terminal_when_absent": True,
                        },
                        "continuation_token": {
                            "response_field": "continuation_token",
                            "request_field": "continuation_token",
                        },
                        "statuses": [
                            {"value": "in_progress", "terminal": False},
                            {"value": "completed", "terminal": True},
                        ],
                    },
                    "journeys": [
                        {
                            "id": "change-driving-licence-address",
                            "title": "Change driving-licence address",
                            "operations": {
                                "start": {"method": "POST", "path": "/start"},
                                "guidance_directory": {
                                    "method": "GET",
                                    "path": "/advertised/guidance",
                                },
                                "guidance": {
                                    "method": "GET",
                                    "path": "/advertised/guidance/{topic}",
                                },
                            },
                        }
                    ],
                }
            ),
            FakeResponse(
                {
                    "version": "1",
                    "topics": [
                        {
                            "id": "postcode-lookup-for-flats",
                            "title": "Using postcode lookup for a flat",
                            "description": "Use for questions about flats.",
                        }
                    ],
                }
            ),
            FakeResponse(
                {
                    "id": "postcode-lookup-for-flats",
                    "title": "Using postcode lookup for a flat",
                    "description": "Use for questions about flats.",
                    "version": "1",
                    "content_type": "text/markdown",
                    "content": "# Flats\n\nPrototype guidance.",
                    "sha256": "a" * 64,
                }
            ),
        ]
    )
    client = JourneyClient("http://journey.test", session=session)

    directory = client.list_guidance("change-driving-licence-address")
    document = client.get_guidance(
        "change-driving-licence-address",
        "postcode-lookup-for-flats",
    )

    assert directory.topics[0].id == "postcode-lookup-for-flats"
    assert document.content_type == "text/markdown"
    assert [call["url"] for call in session.calls] == [
        "http://journey.test/app/dvla/v1/journeys",
        "http://journey.test/advertised/guidance",
        "http://journey.test/advertised/guidance/postcode-lookup-for-flats",
    ]


def test_client_rejects_unsafe_guidance_topic_before_request() -> None:
    """Model-selected topic IDs cannot alter the advertised guidance path."""
    session = FakeSession(
        [
            FakeResponse(
                {
                    "protocol": {"version": "2.0"},
                    "journeys": [
                        {
                            "id": "example-journey",
                            "title": "Example journey",
                            "operations": {
                                "start": {"method": "POST", "path": "/start"},
                                "guidance": {
                                    "method": "GET",
                                    "path": "/guidance/{topic}",
                                },
                            },
                        }
                    ],
                }
            )
        ]
    )
    client = JourneyClient("http://journey.test", session=session)

    with pytest.raises(JourneyProtocolError, match="Guidance topic IDs"):
        client.get_guidance("example-journey", "../admin")

    assert session.calls == []
