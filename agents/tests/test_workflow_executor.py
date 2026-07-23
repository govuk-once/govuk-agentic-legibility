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
from agents.src.workflow_executor.client import JourneyClient
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
from agents.src.workflow_executor.input_provider import JsonCliInputProvider
from agents.src.workflow_executor.state import load_response, save_response


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


class ScriptedInputProvider:
    """Return predetermined results and record interactions."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.interactions: list[Mapping[str, Any]] = []

    def collect(self, interaction: Mapping[str, Any]) -> dict[str, Any]:
        """Return the next scripted interaction result."""
        self.interactions.append(interaction)
        return self.results.pop(0)


class FakeJourneyClient:
    """Journey client that returns predetermined protocol responses."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.started_journey: str | None = None
        self.action_calls: list[dict[str, Any]] = []

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
    session = FakeSession(
        [
            FakeResponse(
                {
                    "protocol": {"version": "2.0"},
                    "journeys": [
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
                    ],
                }
            ),
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
    session = FakeSession([FakeResponse({"status": "finished"})])
    client = JourneyClient("http://journey.test", session=session)

    client.call_action(
        {"method": "POST", "path": "/advertised-action"},
        "latest-token",
        {"confirmed": True},
    )

    assert session.calls[0]["json"] == {
        "continuation_token": "latest-token",
        "result": {"confirmed": True},
    }
    assert session.calls[0]["url"] == "http://journey.test/advertised-action"


def test_executor_uses_next_action_presence_not_status() -> None:
    """Unknown status names do not affect generic executor control flow."""
    client = FakeJourneyClient(
        [
            non_terminal_response("token-1", status="first_unknown_status"),
            non_terminal_response("token-2", status="second_unknown_status"),
            {"status": "another_terminal_name", "result": {"ok": True}},
        ]
    )
    provider = ScriptedInputProvider([{"first": 1}, {"second": 2}])

    response = JourneyExecutor(client).run("example-journey", provider)

    assert response == {"status": "another_terminal_name", "result": {"ok": True}}
    assert [call["continuation_token"] for call in client.action_calls] == [
        "token-1",
        "token-2",
    ]
    assert [call["result"] for call in client.action_calls] == [
        {"first": 1},
        {"second": 2},
    ]


def test_executor_can_suspend_and_resume_without_interpreting_status() -> None:
    """A latest response is sufficient to pause and continue execution."""
    client = FakeJourneyClient(
        [
            non_terminal_response("token-1", status="waiting"),
            non_terminal_response("token-2", status="still_waiting"),
            {"status": "done"},
        ]
    )
    executor = JourneyExecutor(client)

    suspended = executor.run(
        "example-journey",
        ScriptedInputProvider([{"one": 1}]),
        max_interactions=1,
    )
    assert suspended["continuation_token"] == "token-2"

    completed = executor.continue_from(
        suspended,
        ScriptedInputProvider([{"two": 2}]),
    )
    assert completed == {"status": "done"}


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
        [FakeResponse({"detail": "Address not found"}, status_code=404)]
    )
    client = JourneyClient("http://journey.test", session=session)

    with pytest.raises(JourneyHttpError, match="Address not found"):
        client.call_action(
            {"method": "POST", "path": "/next"},
            "token",
            {"postcode": "SW1A 1AA"},
        )


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
