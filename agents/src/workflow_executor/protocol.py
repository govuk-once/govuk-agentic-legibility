"""Parsed rules for the server-driven journey protocol."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agents.src.workflow_executor.errors import JourneyProtocolError
from agents.src.workflow_executor.types import ReadOnlyJsonObject


@dataclass(frozen=True)
class JourneyProtocolDefinition:
    """Machine-readable protocol rules advertised by the journey catalogue."""

    version: str
    next_action_field: str
    terminal_when_absent: bool
    continuation_token_response_field: str
    continuation_token_request_field: str
    terminal_statuses: frozenset[str]
    non_terminal_statuses: frozenset[str]

    def is_terminal(self, response: ReadOnlyJsonObject) -> bool:
        """Return terminality from the advertised status vocabulary.

        The configured next-action field is checked for consistency, but it is not
        itself used to classify the response.
        """
        status = _required_string(response, "status", context="Journey response")
        has_next_action = self.next_action_field in response

        if status in self.terminal_statuses:
            if has_next_action:
                raise JourneyProtocolError(
                    f"Terminal status {status!r} must not include response field "
                    f"{self.next_action_field!r}"
                )
            return True

        if status in self.non_terminal_statuses:
            if self.terminal_when_absent and not has_next_action:
                raise JourneyProtocolError(
                    f"Non-terminal status {status!r} must include response field "
                    f"{self.next_action_field!r}"
                )
            return False

        raise JourneyProtocolError(
            f"Journey response status {status!r} is not advertised by protocol "
            f"version {self.version!r}"
        )


def parse_protocol(catalogue: ReadOnlyJsonObject) -> JourneyProtocolDefinition:
    """Parse the executor rules advertised in a journey catalogue."""
    protocol = _required_mapping(catalogue, "protocol", context="Journey catalogue")
    version = _required_string(protocol, "version", context="Journey protocol")

    terminality = _required_mapping(
        protocol,
        "terminality",
        context="Journey protocol",
    )
    next_action_field = _required_string(
        terminality,
        "next_action_field",
        context="Journey protocol terminality",
    )
    terminal_when_absent = _required_bool(
        terminality,
        "terminal_when_absent",
        context="Journey protocol terminality",
    )

    continuation_token = _required_mapping(
        protocol,
        "continuation_token",
        context="Journey protocol",
    )
    response_field = _required_string(
        continuation_token,
        "response_field",
        context="Journey protocol continuation token",
    )
    request_field = _required_string(
        continuation_token,
        "request_field",
        context="Journey protocol continuation token",
    )

    raw_statuses = protocol.get("statuses")
    if not isinstance(raw_statuses, Sequence) or isinstance(raw_statuses, (str, bytes)):
        raise JourneyProtocolError("Journey protocol field 'statuses' must be a list")

    terminal_statuses: set[str] = set()
    non_terminal_statuses: set[str] = set()
    for raw_status in raw_statuses:
        if not isinstance(raw_status, Mapping):
            raise JourneyProtocolError(
                "Every journey protocol status definition must be an object"
            )
        value = _required_string(
            raw_status,
            "value",
            context="Journey protocol status",
        )
        terminal = _required_bool(
            raw_status,
            "terminal",
            context=f"Journey protocol status {value!r}",
        )
        if value in terminal_statuses or value in non_terminal_statuses:
            raise JourneyProtocolError(
                f"Journey protocol status {value!r} is advertised more than once"
            )
        target = terminal_statuses if terminal else non_terminal_statuses
        target.add(value)

    if not terminal_statuses:
        raise JourneyProtocolError(
            "Journey protocol must advertise at least one terminal status"
        )
    if not non_terminal_statuses:
        raise JourneyProtocolError(
            "Journey protocol must advertise at least one non-terminal status"
        )

    return JourneyProtocolDefinition(
        version=version,
        next_action_field=next_action_field,
        terminal_when_absent=terminal_when_absent,
        continuation_token_response_field=response_field,
        continuation_token_request_field=request_field,
        terminal_statuses=frozenset(terminal_statuses),
        non_terminal_statuses=frozenset(non_terminal_statuses),
    )


def _required_mapping(
    container: Mapping[str, object],
    key: str,
    *,
    context: str,
) -> Mapping[str, object]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise JourneyProtocolError(f"{context} field {key!r} must be an object")
    return value


def _required_string(
    container: Mapping[str, object],
    key: str,
    *,
    context: str,
) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise JourneyProtocolError(f"{context} field {key!r} must be a string")
    return value


def _required_bool(
    container: Mapping[str, object],
    key: str,
    *,
    context: str,
) -> bool:
    value = container.get(key)
    if not isinstance(value, bool):
        raise JourneyProtocolError(f"{context} field {key!r} must be a boolean")
    return value
