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

TRACE_FORMAT_VERSION = "1.0"


class JsonlTraceRecorder:
    """Append raw journey execution events to one local JSONL file.
    Create a recorder and write the run-start event.

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
