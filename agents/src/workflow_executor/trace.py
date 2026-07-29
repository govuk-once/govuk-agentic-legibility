"""Local JSON Lines traces for journey executor runs."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from agents.src.workflow_executor.client import HttpExchange
from agents.src.workflow_executor.types import ReadOnlyJsonObject

TRACE_FORMAT_VERSION = "1.1"


class JsonlTraceRecorder:
    """Append raw journey execution events to one local JSONL file.

    Creating the recorder writes the initial ``run_started`` event.

    Args:
        path: File to which trace events are appended.
        run_id: Identifier shared by every event in this run.
        journey_id: Journey requested by the consumer, if known.
        consumer: Name of the consumer driving the executor.
    """

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        journey_id: str | None,
        consumer: str,
    ) -> None:
        self._path = path
        self._run_id = run_id
        self._sequence = 0
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._append(
            "run_started",
            {
                "trace_version": TRACE_FORMAT_VERSION,
                "journey_id": journey_id,
                "consumer": consumer,
            },
        )

    @classmethod
    def create(
        cls,
        directory: Path,
        *,
        journey_id: str | None,
        consumer: str,
    ) -> JsonlTraceRecorder:
        """Create a recorder with a sortable, unique filename.

        Args:
            directory: Directory in which the trace file is created.
            journey_id: Journey requested by the consumer, if known.
            consumer: Name of the consumer driving the executor.

        Returns:
            A recorder writing to a new JSONL file.
        """
        now = datetime.now(UTC)
        run_id = uuid4().hex
        journey_component = _filename_component(journey_id or "resumed-journey")
        filename = (
            f"{now:%Y%m%dT%H%M%SZ}_{journey_component}_{run_id[:8]}.jsonl"
        )
        return cls(
            directory / filename,
            run_id=run_id,
            journey_id=journey_id,
            consumer=consumer,
        )

    @property
    def path(self) -> Path:
        """Return the trace file path."""
        return self._path

    @property
    def run_id(self) -> str:
        """Return the run identifier shared by all trace events."""
        return self._run_id

    def read_events(self) -> list[dict[str, object]]:
        """Read the raw trace events currently written for this run.

        Returns:
            Decoded JSON objects in sequence order.
        """
        events: list[dict[str, object]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if not isinstance(event, dict):  # pragma: no cover - written internally
                msg = "Journey trace events must be JSON objects"
                raise ValueError(msg)
            events.append(event)
        return events

    def record_exchange(self, exchange: HttpExchange) -> None:
        """Record one journey-service HTTP request and response.

        Args:
            exchange: Sanitised transport exchange emitted by the journey client.
        """
        response: dict[str, object] = {
            "status_code": exchange.status_code,
            "body": exchange.response_body,
        }
        if exchange.error is not None:
            response["error"] = exchange.error

        self._append(
            "http_exchange",
            {
                "request": {
                    "method": exchange.method,
                    "path": exchange.path,
                    "body": exchange.request_body,
                },
                "response": response,
                "duration_ms": round(exchange.duration_ms, 3),
            },
        )

    def record_user_message(
        self,
        *,
        interaction_id: str | None,
        message: str,
    ) -> None:
        """Record natural-language input supplied for the current interaction.

        Args:
            interaction_id: Current service interaction identifier, when available.
            message: User message sent to the interaction assistant.
        """
        self._append(
            "user_message",
            {
                "interaction_id": interaction_id,
                "message": message,
            },
        )

    def record_agent_invoked(
        self,
        *,
        model_id: str,
        prompt_id: str,
        interaction: ReadOnlyJsonObject,
        conversation: list[dict[str, object]],
        user_message: str,
    ) -> None:
        """Record the exact application-level context supplied to an assistant.

        Args:
            model_id: Configured model or inference-profile identifier.
            prompt_id: Identifier of the version-controlled system prompt.
            interaction: Current service interaction and input schema.
            conversation: Earlier user-visible conversation messages.
            user_message: Latest user message interpreted by the assistant.
        """
        self._append(
            "agent_invoked",
            {
                "model_id": model_id,
                "prompt_id": prompt_id,
                "input": {
                    "conversation": conversation,
                    "user_message": user_message,
                    "interaction": dict(interaction),
                },
            },
        )

    def record_agent_responded(
        self,
        *,
        model_id: str,
        action: ReadOnlyJsonObject,
        duration_ms: float,
    ) -> None:
        """Record the validated structured action returned by an assistant.

        Args:
            model_id: Configured model or inference-profile identifier.
            action: Validated structured assistance action.
            duration_ms: End-to-end assistant invocation duration.
        """
        self._append(
            "agent_responded",
            {
                "model_id": model_id,
                "action": dict(action),
                "duration_ms": round(duration_ms, 3),
            },
        )

    def record_agent_failed(
        self,
        *,
        model_id: str | None,
        error: str,
        duration_ms: float | None = None,
    ) -> None:
        """Record a failed or unavailable assistant invocation.

        Args:
            model_id: Configured model identifier, when one was available.
            error: Application-level failure description.
            duration_ms: Invocation duration when a model call was attempted.
        """
        event: dict[str, object] = {
            "model_id": model_id,
            "error": error,
        }
        if duration_ms is not None:
            event["duration_ms"] = round(duration_ms, 3)
        self._append("agent_failed", event)

    def record_proposal_reviewed(
        self,
        *,
        interaction_id: str | None,
        proposed_values: ReadOnlyJsonObject,
        submitted_values: ReadOnlyJsonObject,
    ) -> None:
        """Record whether a user changed an agent proposal before submission.

        Args:
            interaction_id: Current service interaction identifier, when available.
            proposed_values: Values returned by the assistant.
            submitted_values: Values approved or edited by the user.
        """
        proposed = dict(proposed_values)
        submitted = dict(submitted_values)
        changed_fields = sorted(
            field_name
            for field_name, proposed_value in proposed.items()
            if submitted.get(field_name) != proposed_value
        )
        self._append(
            "proposal_reviewed",
            {
                "interaction_id": interaction_id,
                "proposed_values": proposed,
                "submitted_values": submitted,
                "changed": bool(changed_fields),
                "changed_fields": changed_fields,
            },
        )

    def record_result_submitted(
        self,
        *,
        interaction_id: str | None,
        result: ReadOnlyJsonObject,
        source: str,
    ) -> None:
        """Record the browser-level result sent to the executor.

        Args:
            interaction_id: Current service interaction identifier, when available.
            result: Reviewed values submitted by the browser.
            source: Whether the result was manual or based on an agent proposal.
        """
        self._append(
            "result_submitted",
            {
                "interaction_id": interaction_id,
                "source": source,
                "result": dict(result),
            },
        )

    def record_finished(self, response: ReadOnlyJsonObject) -> None:
        """Record successful arrival at a terminal journey response.

        Args:
            response: Validated terminal response returned by the journey service.
        """
        self._append(
            "run_finished",
            {"terminal_status": response.get("status")},
        )

    def record_stopped(
        self,
        response: ReadOnlyJsonObject,
        *,
        reason: str,
    ) -> None:
        """Record that the consumer stopped before a terminal response.

        Args:
            response: Latest validated non-terminal service response.
            reason: Consumer-level reason for stopping the run.
        """
        interaction = response.get("interaction")
        interaction_id = (
            interaction.get("id") if isinstance(interaction, Mapping) else None
        )
        self._append(
            "run_stopped",
            {
                "reason": reason,
                "status": response.get("status"),
                "interaction_id": interaction_id,
            },
        )

    def _append(self, event_type: str, event: dict[str, object]) -> None:
        payload = {
            "run_id": self._run_id,
            "sequence": self._sequence,
            "timestamp": _timestamp(),
            "type": event_type,
            **event,
        }
        with self._path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(payload, ensure_ascii=False))
            trace_file.write("\n")
        self._sequence += 1


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _filename_component(value: str) -> str:
    component = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    return component or "journey"
