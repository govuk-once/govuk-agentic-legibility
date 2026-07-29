"""Tests for catalogue-driven journey protocol rules."""

from __future__ import annotations

from typing import Any

import pytest

from agents.src.workflow_executor.errors import JourneyProtocolError
from agents.src.workflow_executor.protocol import (
    JourneyProtocolDefinition,
    parse_protocol,
)
from agents.src.workflow_executor.types import ReadOnlyJsonObject


def protocol_catalogue() -> dict[str, Any]:
    """Build a machine-readable protocol catalogue for tests."""
    return {
        "protocol": {
            "version": "2.0",
            "terminality": {
                "next_action_field": "continue_with",
                "terminal_when_absent": True,
            },
            "continuation_token": {
                "response_field": "cursor",
                "request_field": "cursor",
            },
            "statuses": [
                {"value": "working", "terminal": False},
                {"value": "done", "terminal": True},
                {"value": "declined", "terminal": True},
            ],
        },
        "journeys": [],
    }


def test_protocol_parses_terminal_statuses_and_field_names() -> None:
    """Control-flow rules come from the catalogue rather than executor constants."""
    protocol = parse_protocol(protocol_catalogue())

    assert protocol.next_action_field == "continue_with"
    assert protocol.continuation_token_response_field == "cursor"
    assert protocol.continuation_token_request_field == "cursor"
    assert protocol.terminal_statuses == {"done", "declined"}
    assert protocol.non_terminal_statuses == {"working"}


def test_protocol_uses_advertised_status_to_classify_response() -> None:
    """The advertised terminal flag, not a field-name test, controls terminality."""
    protocol = parse_protocol(protocol_catalogue())

    assert protocol.is_terminal({"status": "done"}) is True
    assert (
        protocol.is_terminal(
            {
                "status": "working",
                "continue_with": {"method": "POST", "path": "/next"},
            }
        )
        is False
    )


def test_protocol_rejects_status_and_action_inconsistency() -> None:
    """Status terminality and advertised actions must agree."""
    protocol = parse_protocol(protocol_catalogue())

    with pytest.raises(JourneyProtocolError, match="Terminal status"):
        protocol.is_terminal(
            {
                "status": "done",
                "continue_with": {"method": "POST", "path": "/unexpected"},
            }
        )

    with pytest.raises(JourneyProtocolError, match="Non-terminal status"):
        protocol.is_terminal({"status": "working"})


def test_protocol_rejects_unadvertised_status() -> None:
    """A response cannot invent a status outside the exhaustive vocabulary."""
    protocol = parse_protocol(protocol_catalogue())

    with pytest.raises(JourneyProtocolError, match="is not advertised"):
        protocol.is_terminal({"status": "mystery"})


class RecordingClient:
    """Minimal protocol-aware client used to exercise the executor."""

    def __init__(self) -> None:
        self.protocol = parse_protocol(protocol_catalogue())
        self.calls: list[dict[str, Any]] = []

    def get_protocol(self) -> JourneyProtocolDefinition:
        """Return the configured test protocol."""
        return self.protocol

    def start_journey(self, _journey_id: str) -> dict[str, Any]:
        """Return a response using deliberately non-default field names."""
        return {
            "status": "working",
            "cursor": "token-1",
            "interaction": {"id": "example"},
            "continue_with": {"method": "POST", "path": "/next"},
        }

    def call_action(
        self,
        action: ReadOnlyJsonObject,
        continuation_token: str,
        result: ReadOnlyJsonObject,
    ) -> dict[str, Any]:
        """Record the supplied protocol values and terminate the journey."""
        self.calls.append(
            {
                "action": dict(action),
                "continuation_token": continuation_token,
                "result": dict(result),
            }
        )
        return {"status": "done"}


def test_executor_uses_advertised_action_and_token_fields() -> None:
    """The executor does not assume next_action or continuation_token names."""
    from agents.src.workflow_executor.executor import JourneyExecutor

    client = RecordingClient()
    executor = JourneyExecutor(client)

    response = executor.start("example")
    completed = executor.submit(response, {"answer": True})

    assert completed == {"status": "done"}
    assert client.calls == [
        {
            "action": {"method": "POST", "path": "/next"},
            "continuation_token": "token-1",
            "result": {"answer": True},
        }
    ]
