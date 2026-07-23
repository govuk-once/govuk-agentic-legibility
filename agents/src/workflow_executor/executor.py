"""Journey-agnostic execution of server-driven interactions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from agents.src.workflow_executor.errors import JourneyProtocolError
from agents.src.workflow_executor.input_provider import InputProvider
from agents.src.workflow_executor.types import JsonObject, ReadOnlyJsonObject

ResponseObserver = Callable[[ReadOnlyJsonObject], None]


class JourneyClientProtocol(Protocol):
    """HTTP operations required by the generic executor."""

    def start_journey(self, journey_id: str) -> JsonObject:
        """Start a journey and return its first response."""

    def call_action(
        self,
        action: ReadOnlyJsonObject,
        continuation_token: str,
        result: ReadOnlyJsonObject,
    ) -> JsonObject:
        """Submit an interaction result and return the next response."""


class JourneyExecutor:
    """Execute successive interactions without interpreting a journey graph.
    Initialise the executor with a journey service client.

        Args:
            client: Client used to start journeys and follow advertised actions.
    """

    def __init__(self, client: JourneyClientProtocol) -> None:
        
        self._client = client

    def run(
        self,
        journey_id: str,
        input_provider: InputProvider,
        *,
        max_interactions: int | None = None,
        on_response: ResponseObserver | None = None,
    ) -> JsonObject:
        """Start and execute a journey until it terminates or is suspended.

        Args:
            journey_id: Journey identifier from the service catalogue.
            input_provider: Consumer-specific implementation that presents content and
                collects data conforming to the supplied input schema.
            max_interactions: Optional interaction limit before returning the latest
                response for later resumption.
            on_response: Optional callback invoked for every service response.

        Returns:
            A terminal response, or the latest non-terminal response when execution is
            deliberately suspended.
        """
        response = self._client.start_journey(journey_id)
        return self.continue_from(
            response,
            input_provider,
            max_interactions=max_interactions,
            on_response=on_response,
        )

    def continue_from(
        self,
        response: ReadOnlyJsonObject,
        input_provider: InputProvider,
        *,
        max_interactions: int | None = None,
        on_response: ResponseObserver | None = None,
    ) -> JsonObject:
        """Continue from a previously returned journey response.

        Terminality is determined exclusively by the absence of `next_action`. The
        executor does not branch on journey status, step identifiers or domain values.

        Args:
            response: Latest complete response returned by the journey service.
            input_provider: Consumer-specific interaction handler.
            max_interactions: Optional interaction limit before returning.
            on_response: Optional callback invoked for every service response.

        Returns:
            A terminal response, or the latest response after `max_interactions`.

        Raises:
            JourneyProtocolError: If a non-terminal response lacks the shared protocol
                fields required to continue.
            ValueError: If `max_interactions` is negative.
        """
        if max_interactions is not None and max_interactions < 0:
            msg = "max_interactions must be zero or greater"
            raise ValueError(msg)

        current = dict(response)
        if on_response is not None:
            on_response(current)

        interactions_processed = 0
        while "next_action" in current:
            if (
                max_interactions is not None
                and interactions_processed >= max_interactions
            ):
                return current

            action = _required_mapping(current, "next_action")
            interaction = _required_mapping(current, "interaction")
            continuation_token = _required_string(current, "continuation_token")

            result = input_provider.collect(interaction)
            if not isinstance(result, dict):
                msg = "Input providers must return a JSON object"
                raise JourneyProtocolError(msg)

            current = self._client.call_action(
                action,
                continuation_token,
                result,
            )
            interactions_processed += 1
            if on_response is not None:
                on_response(current)

        return current


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
