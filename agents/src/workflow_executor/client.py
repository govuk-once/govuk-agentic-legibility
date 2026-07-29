"""HTTP client for the server-driven journey protocol."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlsplit

import requests

from agents.src.workflow_executor.errors import (
    JourneyHttpError,
    JourneyNotFoundError,
    JourneyProtocolError,
)
from agents.src.workflow_executor.protocol import (
    JourneyProtocolDefinition,
    parse_protocol,
)
from agents.src.workflow_executor.types import JsonObject, ReadOnlyJsonObject

CATALOGUE_PATH = "/app/dvla/v1/journeys"
SUPPORTED_PROTOCOL_VERSIONS = frozenset({"2.0"})


class HttpResponse(Protocol):
    """Response operations used by the journey client."""

    text: str
    status_code: int

    def raise_for_status(self) -> None:
        """Raise an exception for a non-successful response."""

    def json(self) -> object:
        """Decode the response body as JSON."""


class HttpSession(Protocol):
    """HTTP session operations used by the journey client."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json: JsonObject | None,
        timeout: float,
    ) -> HttpResponse:
        """Send an HTTP request."""


@dataclass(frozen=True)
class HttpExchange:
    """One sanitised HTTP exchange with the journey service."""

    method: str
    path: str
    request_body: object | None
    status_code: int | None
    response_body: object | None
    duration_ms: float
    error: str | None = None


HttpExchangeObserver = Callable[[HttpExchange], None]


@dataclass(frozen=True)
class Operation:
    """An HTTP operation advertised by the journey service."""

    method: str
    path: str


@dataclass(frozen=True)
class JourneyDefinition:
    """The catalogue information required to start a journey."""

    journey_id: str
    title: str
    start: Operation


class JourneyClient:
    """Call a service implementing the server-driven journey protocol.
            Args:
            base_url: Base URL of the journey service.
            session: Optional HTTP session for tests and connection reuse.
            headers: Headers applied to every request, such as authentication material.
            timeout_seconds: Timeout applied to each HTTP request.
            supported_protocol_versions: Protocol versions accepted by this client.
            on_exchange: Optional observer for sanitised HTTP request/response traces.

        Raises:
            ValueError: If the base URL is missing a scheme or host.
    """

    def __init__(
        self,
        base_url: str,
        *,
        session: HttpSession | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 10.0,
        supported_protocol_versions: frozenset[str] = SUPPORTED_PROTOCOL_VERSIONS,
        on_exchange: HttpExchangeObserver | None = None,
    ) -> None:

        parsed_url = urlsplit(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            msg = "base_url must be an absolute HTTP or HTTPS URL"
            raise ValueError(msg)

        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._headers = dict(headers or {})
        self._timeout_seconds = timeout_seconds
        self._supported_protocol_versions = supported_protocol_versions
        self._on_exchange = on_exchange
        self._catalogue: JsonObject | None = None
        self._protocol: JourneyProtocolDefinition | None = None

    def get_catalogue(self) -> JsonObject:
        """Retrieve and validate the service journey catalogue.

        Returns:
            The journey catalogue.

        Raises:
            JourneyProtocolError: If the response is not a JSON object or uses an
                unsupported protocol version.
            JourneyHttpError: If the catalogue request fails.
        """
        if self._catalogue is not None:
            return self._catalogue

        catalogue = self._request("GET", CATALOGUE_PATH)
        protocol = _required_mapping(catalogue, "protocol")
        version = _required_string(protocol, "version")
        if version not in self._supported_protocol_versions:
            supported = ", ".join(sorted(self._supported_protocol_versions))
            msg = (
                f"Unsupported journey protocol version {version!r}; "
                f"supported: {supported}"
            )
            raise JourneyProtocolError(msg)
        self._protocol = parse_protocol(catalogue)
        self._catalogue = catalogue
        return self._catalogue

    def get_protocol(self) -> JourneyProtocolDefinition:
        """Return the parsed protocol rules advertised by the service."""
        catalogue = self.get_catalogue()
        if self._protocol is None:  # pragma: no cover - set by get_catalogue
            self._protocol = parse_protocol(catalogue)
        return self._protocol

    def get_journey(self, journey_id: str) -> JourneyDefinition:
        """Find a journey in the service catalogue.

        Args:
            journey_id: Stable journey identifier advertised by the service.

        Returns:
            The matching journey definition.

        Raises:
            JourneyNotFoundError: If no journey with that identifier is advertised.
            JourneyProtocolError: If the catalogue entry is malformed.
        """
        catalogue = self.get_catalogue()
        journeys = catalogue.get("journeys")
        if not isinstance(journeys, list):
            msg = "Journey catalogue field 'journeys' must be a list"
            raise JourneyProtocolError(msg)

        for raw_journey in journeys:
            if not isinstance(raw_journey, Mapping):
                continue
            if raw_journey.get("id") != journey_id:
                continue

            operations = _required_mapping(raw_journey, "operations")
            start = _parse_operation(_required_mapping(operations, "start"))
            return JourneyDefinition(
                journey_id=journey_id,
                title=_required_string(raw_journey, "title"),
                start=start,
            )

        raise JourneyNotFoundError(f"Journey {journey_id!r} is not advertised")

    def start_journey(self, journey_id: str) -> JsonObject:
        """Start an advertised journey.

        Args:
            journey_id: Stable journey identifier advertised in the catalogue.

        Returns:
            The first runtime response from the journey service.
        """
        journey = self.get_journey(journey_id)
        return self._request(journey.start.method, journey.start.path)

    def call_action(
        self,
        action: ReadOnlyJsonObject,
        continuation_token: str,
        result: ReadOnlyJsonObject,
    ) -> JsonObject:
        """Submit one interaction result to the advertised next action.

        Args:
            action: The `next_action` object from the latest service response.
            continuation_token: Token from the latest service response.
            result: Data collected for the current interaction.

        Returns:
            The next runtime response selected by the service.

        Raises:
            JourneyProtocolError: If the advertised action is malformed or unsafe.
        """
        operation = _parse_operation(action)
        token_request_field = self.get_protocol().continuation_token_request_field
        body: JsonObject = {
            token_request_field: continuation_token,
            "result": dict(result),
        }
        return self._request(operation.method, operation.path, json_body=body)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: JsonObject | None = None,
    ) -> JsonObject:
        method = method.upper()
        _validate_relative_path(path)
        url = f"{self._base_url}{path}"
        started_at = perf_counter()

        try:
            response = self._session.request(
                method,
                url,
                headers=self._headers,
                json=json_body,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            message = f"Journey service request failed: {method} {path}"
            self._emit_exchange(
                method=method,
                path=path,
                request_body=json_body,
                status_code=None,
                response_body=None,
                started_at=started_at,
                error=message,
            )
            raise JourneyHttpError(message) from exc

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            response_body = _response_body(response) # type: ignore
            status_code = response.status_code
            detail = _body_detail(response_body)
            message = f"Journey service request failed: {method} {path}"
            message += f" returned {status_code}"
            if detail:
                message += f": {detail}"
            self._emit_exchange(
                method=method,
                path=path,
                request_body=json_body,
                status_code=status_code,
                response_body=response_body,
                started_at=started_at,
                error=message,
            )
            raise JourneyHttpError(message) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            msg = f"Journey service returned non-JSON content for {method} {path}"
            self._emit_exchange(
                method=method,
                path=path,
                request_body=json_body,
                status_code=response.status_code,
                response_body=response.text.strip() or None,
                started_at=started_at,
                error=msg,
            )
            raise JourneyProtocolError(msg) from exc

        if not isinstance(payload, dict):
            msg = f"Journey service response for {method} {path} must be a JSON object"
            self._emit_exchange(
                method=method,
                path=path,
                request_body=json_body,
                status_code=response.status_code,
                response_body=payload,
                started_at=started_at,
                error=msg,
            )
            raise JourneyProtocolError(msg)

        self._emit_exchange(
            method=method,
            path=path,
            request_body=json_body,
            status_code=response.status_code,
            response_body=payload,
            started_at=started_at,
        )
        return payload

    def _emit_exchange(
        self,
        *,
        method: str,
        path: str,
        request_body: object | None,
        status_code: int | None,
        response_body: object | None,
        started_at: float,
        error: str | None = None,
    ) -> None:
        if self._on_exchange is None:
            return

        redacted_fields: frozenset[str] = frozenset()
        if self._protocol is not None:
            redacted_fields = frozenset(
                {
                    self._protocol.continuation_token_request_field,
                    self._protocol.continuation_token_response_field,
                }
            )

        self._on_exchange(
            HttpExchange(
                method=method,
                path=path,
                request_body=_redact_fields(request_body, redacted_fields),
                status_code=status_code,
                response_body=_redact_fields(response_body, redacted_fields),
                duration_ms=(perf_counter() - started_at) * 1000,
                error=error,
            )
        )


def _parse_operation(raw_operation: ReadOnlyJsonObject) -> Operation:
    method = _required_string(raw_operation, "method").upper()
    path = _required_string(raw_operation, "path")
    _validate_relative_path(path)
    return Operation(method=method, path=path)


def _validate_relative_path(path: str) -> None:
    parsed_path = urlsplit(path)
    if not path.startswith("/") or parsed_path.scheme or parsed_path.netloc:
        msg = (
            "Journey operations must use absolute paths on the configured "
            "service origin"
        )
        raise JourneyProtocolError(msg)


def _required_mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise JourneyProtocolError(f"Journey contract field {key!r} must be an object")
    return value


def _required_string(container: Mapping[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise JourneyProtocolError(f"Journey contract field {key!r} must be a string")
    return value


def _response_body(response: HttpResponse) -> object | None:
    try:
        return response.json()
    except (TypeError, ValueError):
        return response.text.strip() or None


def _body_detail(body: object | None) -> str | None:
    if isinstance(body, Mapping):
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
    if isinstance(body, str):
        return body or None
    return None


def _redact_fields(value: object, fields: frozenset[str]) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): "[redacted]"
            if key in fields
            else _redact_fields(item, fields)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_fields(item, fields) for item in value]
    return value
