"""Thin HTTP adapter for browser-driven journey executor runs."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from agents.src.workflow_executor.client import HttpExchangeObserver, JourneyClient
from agents.src.workflow_executor.config import (
    load_executor_environment,
    resolve_base_url,
)
from agents.src.workflow_executor.errors import (
    JourneyExecutorError,
    JourneyNotFoundError,
)
from agents.src.workflow_executor.executor import (
    JourneyClientProtocol,
    JourneyExecutor,
)
from agents.src.workflow_executor.trace import JsonlTraceRecorder
from agents.src.workflow_executor.types import JsonObject, ReadOnlyJsonObject

DEFAULT_TRACE_DIRECTORY = Path(".traces")
DEFAULT_FRONTEND_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)

JourneyClientFactory: TypeAlias = Callable[
    [HttpExchangeObserver | None],
    JourneyClientProtocol,
]


class StartRunRequest(BaseModel):
    """Request for a new journey run."""

    model_config = ConfigDict(extra="forbid")

    journey_id: str = Field(min_length=1)


class SubmitResultRequest(BaseModel):
    """Result supplied for the current interaction."""

    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any]


class RunResponse(BaseModel):
    """Frontend-facing state of an active or completed run."""

    run_id: str
    journey_id: str
    status: str
    terminal: bool
    interaction: JsonObject | None


@dataclass
class _Run:
    journey_id: str
    executor: JourneyExecutor
    response: JsonObject
    trace: JsonlTraceRecorder


class _RunCompletedError(RuntimeError):
    pass


class JourneyRunService:
    """Drive process-local runs for a browser or other HTTP consumer.

    Args:
        trace_directory: Local directory used for raw JSONL traces.
        client_factory: Factory creating one traced journey client per run.
    """

    def __init__(
        self,
        *,
        trace_directory: Path,
        client_factory: JourneyClientFactory,
    ) -> None:
        self._trace_directory = trace_directory
        self._client_factory = client_factory
        self._runs: dict[str, _Run] = {}

    def start(self, journey_id: str) -> RunResponse:
        """Start a journey and return its first interaction.

        Args:
            journey_id: Journey identifier advertised by the service catalogue.

        Returns:
            First interaction or terminal response.

        Raises:
            JourneyExecutorError: If the journey cannot be started or validated.
        """
        trace = JsonlTraceRecorder.create(
            self._trace_directory,
            journey_id=journey_id,
            consumer="http_frontend",
        )
        executor = JourneyExecutor(self._client_factory(trace.record_exchange))
        response = executor.start(journey_id)
        run = _Run(journey_id, executor, response, trace)
        self._runs[trace.run_id] = run
        if executor.is_terminal(response):
            trace.record_finished(response)
        return self._view(trace.run_id, run)

    def submit(
        self,
        run_id: str,
        result: ReadOnlyJsonObject,
    ) -> RunResponse:
        """Submit a result and return the next service-selected interaction.

        Args:
            run_id: Process-local run identifier.
            result: JSON object collected by the current consumer.

        Returns:
            Next interaction or terminal response.

        Raises:
            KeyError: If the run is not held by this process.
            _RunCompletedError: If the run has already reached terminal state.
        """
        run = self._runs[run_id]
        if run.executor.is_terminal(run.response):
            raise _RunCompletedError

        run.response = run.executor.submit(run.response, result)
        if run.executor.is_terminal(run.response):
            run.trace.record_finished(run.response)
        return self._view(run_id, run)

    def trace_events(self, run_id: str) -> list[dict[str, object]]:
        """Return raw events recorded for a process-local run.

        Args:
            run_id: Process-local run identifier.

        Returns:
            Ordered raw trace events.

        Raises:
            KeyError: If the run is not held by this process.
        """
        return self._runs[run_id].trace.read_events()

    @staticmethod
    def _view(run_id: str, run: _Run) -> RunResponse:
        terminal = run.executor.is_terminal(run.response)
        raw_status = run.response.get("status")
        if not isinstance(raw_status, str):  # pragma: no cover - protocol validated
            msg = "Journey response field 'status' must be a string"
            raise JourneyExecutorError(msg)
        return RunResponse(
            run_id=run_id,
            journey_id=run.journey_id,
            status=raw_status,
            terminal=terminal,
            interaction=run.executor.current_interaction(run.response),
        )


def create_app(
    *,
    base_url: str | None = None,
    trace_directory: Path | None = None,
    run_service: JourneyRunService | None = None,
) -> FastAPI:
    """Create the HTTP adapter used by the SvelteKit prototype.

    Args:
        base_url: Optional explicit journey-service URL.
        trace_directory: Optional local trace directory.
        run_service: Optional injected service used by tests.

    Returns:
        Configured FastAPI application.
    """
    if run_service is None:
        load_executor_environment()
        resolved_url = resolve_base_url(base_url)
        configured_service = JourneyRunService(
            trace_directory=trace_directory or _environment_trace_directory(),
            client_factory=lambda observer: JourneyClient(
                resolved_url,
                on_exchange=observer,
            ),
        )
    else:
        configured_service = run_service

    app = FastAPI(title="Journey executor prototype API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEFAULT_FRONTEND_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/healthcheck")
    def healthcheck() -> dict[str, str]:
        """Return a simple process health response.

        Returns:
            Static health response.
        """
        return {"status": "ok"}

    @app.post(
        "/api/journey-runs",
        response_model=RunResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def start_run(request: StartRunRequest) -> RunResponse:
        """Start one process-local journey run.

        Args:
            request: Journey identifier supplied by the frontend.

        Returns:
            First interaction or terminal response.

        Raises:
            HTTPException: If the journey cannot be found or started.
        """
        try:
            return configured_service.start(request.journey_id)
        except JourneyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JourneyExecutorError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post(
        "/api/journey-runs/{run_id}/results",
        response_model=RunResponse,
    )
    def submit_result(run_id: str, request: SubmitResultRequest) -> RunResponse:
        """Submit the current interaction result for a run.

        Args:
            run_id: Process-local run identifier.
            request: Result supplied by the frontend.

        Returns:
            Next interaction or terminal response.

        Raises:
            HTTPException: If the run is unavailable, complete or cannot advance.
        """
        try:
            return configured_service.submit(run_id, request.result)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Journey run not found") from exc
        except _RunCompletedError as exc:
            raise HTTPException(
                status_code=409,
                detail="Journey run has already completed",
            ) from exc
        except JourneyExecutorError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/journey-runs/{run_id}/trace")
    def get_trace(run_id: str) -> dict[str, object]:
        """Return raw local trace events for a run.

        Args:
            run_id: Process-local run identifier.

        Returns:
            Run identifier and ordered raw trace events.

        Raises:
            HTTPException: If the run is not held by this process.
        """
        try:
            events = configured_service.trace_events(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Journey run not found") from exc
        return {"run_id": run_id, "events": events}

    return app


def _environment_trace_directory() -> Path:
    value = os.environ.get("JOURNEY_TRACE_DIR")
    return Path(value) if value else DEFAULT_TRACE_DIRECTORY
