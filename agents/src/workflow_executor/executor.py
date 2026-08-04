"""Stepwise execution of server-driven service journeys."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from agents.src.workflow_executor.errors import JourneyProtocolError
from agents.src.workflow_executor.protocol import JourneyProtocolDefinition
from agents.src.workflow_executor.types import JsonObject, ReadOnlyJsonObject


class JourneyClientProtocol(Protocol):
    """HTTP operations required by the generic executor."""

    def start_journey(self, journey_id: str) -> JsonObject:
        """Start a journey and return its first response."""

    def get_protocol(self) -> JourneyProtocolDefinition:
        """Return the protocol rules advertised by the journey service."""

    def call_action(
        self,
        action: ReadOnlyJsonObject,
        continuation_token: str,
        result: ReadOnlyJsonObject,
    ) -> JsonObject:
        """Submit an interaction result and return the next response."""


class JourneyExecutor:
    """Advance a server-driven journey one operation at a time.

    The executor does not collect input or own a long-running execution loop. A CLI,
    web application, agent or test harness can start a journey, inspect the current
    interaction and later submit a result.

    Args:
        client: Client used to start journeys and follow advertised actions.
    """

    def __init__(self, client: JourneyClientProtocol) -> None:
        self._client = client

    def start(self, journey_id: str) -> JsonObject:
        """Start a journey and return its first validated service response.

        Args:
            journey_id: Journey identifier advertised by the service catalogue.

        Returns:
            The first non-terminal interaction or terminal journey response.

        Raises:
            JourneyProtocolError: If the service returns a malformed response.
        """
        response = self._client.start_journey(journey_id)
        self._validate_response(response)
        return response

    def submit(
        self,
        response: ReadOnlyJsonObject,
        result: ReadOnlyJsonObject,
    ) -> JsonObject:
        """Submit a result for the interaction in the latest service response.

        The operation, continuation token and journey transition are all taken from
        the supplied service response using the field names advertised by the
        protocol catalogue. The executor does not branch on journey-specific status
        names, interaction identifiers or domain values.

        Args:
            response: Latest complete response returned by the journey service.
            result: JSON object produced by the current consumer.

        Returns:
            The next validated response selected by the journey service.

        Raises:
            JourneyProtocolError: If the response is terminal or does not contain the
                fields required by the shared protocol.
        """
        self._validate_response(response)
        if self.is_terminal(response):
            msg = "Cannot submit a result for a terminal journey response"
            raise JourneyProtocolError(msg)
        if not isinstance(result, Mapping):
            msg = "Journey interaction results must be JSON objects"
            raise JourneyProtocolError(msg)

        protocol = self._client.get_protocol()
        action = _required_mapping(response, protocol.next_action_field)
        continuation_token = _required_string(
            response,
            protocol.continuation_token_response_field,
        )
        next_response = self._client.call_action(
            action,
            continuation_token,
            result,
        )
        self._validate_response(next_response)
        return next_response

    def current_interaction(
        self,
        response: ReadOnlyJsonObject,
    ) -> JsonObject | None:
        """Return the current interaction, or ``None`` for a terminal response.

        Args:
            response: Latest complete response returned by the journey service.

        Returns:
            A copy of the current interaction, or ``None`` when the journey is
            terminal.

        Raises:
            JourneyProtocolError: If a non-terminal response is malformed.
        """
        self._validate_response(response)
        if self.is_terminal(response):
            return None
        return dict(_required_mapping(response, "interaction"))

    def is_terminal(self, response: ReadOnlyJsonObject) -> bool:
        """Return terminality using the protocol advertised by the service."""
        return self._client.get_protocol().is_terminal(response)

    def _validate_response(self, response: ReadOnlyJsonObject) -> None:
        if self.is_terminal(response):
            return

        protocol = self._client.get_protocol()
        _required_mapping(response, protocol.next_action_field)
        _required_mapping(response, "interaction")
        _required_string(response, protocol.continuation_token_response_field)


def _required_mapping(
    container: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise JourneyProtocolError(
            f"Non-terminal response field {key!r} must be an object"
        )
    return value


def _required_string(container: Mapping[str, object], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise JourneyProtocolError(
            f"Non-terminal response field {key!r} must be a string"
        )
    return value
