"""Thin HTTP adapter for browser-driven journey executor runs."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, TypeAlias

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from agents.src.interaction_assistant import (
    AssistanceAction,
    AssistanceRequest,
    ConversationMessage,
    InteractionAssistant,
    InteractionAssistantError,
    validate_assistance_action,
)
from agents.src.interaction_assistant.config import create_environment_assistant
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


class AssistanceApiRequest(BaseModel):
    """Natural-language input for the current journey interaction."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    conversation: list[ConversationMessage] = Field(default_factory=list)


class AssistanceApiResponse(BaseModel):
    """Structured assistance returned without advancing the journey."""

    action: AssistanceAction
    model_id: str
    prompt_id: str
    duration_ms: float


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
    latest_proposal: JsonObject | None = None


class _RunCompletedError(RuntimeError):
    pass


class _AssistantUnavailableError(RuntimeError):
    pass


class JourneyRunService:
    """Drive process-local runs for a browser or other HTTP consumer.

    Args:
        trace_directory: Local directory used for raw JSONL traces.
        client_factory: Factory creating one traced journey client per run.
        assistant: Optional bounded assistant for the current interaction.
    """

    def __init__(
        self,
        *,
        trace_directory: Path,
        client_factory: JourneyClientFactory,
        assistant: InteractionAssistant | None = None,
    ) -> None:
        self._trace_directory = trace_directory
        self._client_factory = client_factory
        self._assistant = assistant
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
            consumer="agent_assisted_http_frontend",
        )
        executor = JourneyExecutor(self._client_factory(trace.record_exchange))
        response = executor.start(journey_id)
        run = _Run(journey_id, executor, response, trace)
        self._runs[trace.run_id] = run
        if executor.is_terminal(response):
            trace.record_finished(response)
        return self._view(trace.run_id, run)

    def assist(
        self,
        run_id: str,
        *,
        message: str,
        conversation: list[ConversationMessage],
    ) -> AssistanceApiResponse:
        """Ask the assistant to propose values for the current interaction.

        Args:
            run_id: Process-local run identifier.
            message: Latest user message to interpret.
            conversation: Earlier user-visible conversation messages.

        Returns:
            Structured assistance without advancing the journey.

        Raises:
            KeyError: If the run is not held by this process.
            _RunCompletedError: If the run has already reached terminal state.
            _AssistantUnavailableError: If no assistant model is configured.
            InteractionAssistantError: If the assistant cannot return a valid action.
        """
        run = self._runs[run_id]
        if run.executor.is_terminal(run.response):
            raise _RunCompletedError

        interaction = run.executor.current_interaction(run.response)
        if interaction is None:  # pragma: no cover - terminality checked above
            raise _RunCompletedError
        interaction_id = _interaction_id(interaction)
        run.trace.record_user_message(
            interaction_id=interaction_id,
            message=message,
        )

        if self._assistant is None:
            error = "Interaction assistant is not configured"
            run.trace.record_agent_failed(model_id=None, error=error)
            raise _AssistantUnavailableError(error)

        request = AssistanceRequest(
            user_message=message,
            conversation=conversation,
            interaction=interaction,
        )
        conversation_payload: list[dict[str, object]] = [
            item.model_dump(mode="json") for item in conversation
        ]
        run.trace.record_agent_invoked(
            model_id=self._assistant.model_id,
            prompt_id=self._assistant.prompt_id,
            interaction=interaction,
            conversation=conversation_payload,
            user_message=message,
        )

        started_at = perf_counter()
        try:
            action = validate_assistance_action(
                self._assistant.assist(request),
                interaction,
            )
        except InteractionAssistantError as exc:
            duration_ms = (perf_counter() - started_at) * 1000
            run.trace.record_agent_failed(
                model_id=self._assistant.model_id,
                error=str(exc),
                duration_ms=duration_ms,
            )
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        action_payload = action.model_dump(mode="json")
        run.trace.record_agent_responded(
            model_id=self._assistant.model_id,
            action=action_payload,
            duration_ms=duration_ms,
        )
        run.latest_proposal = (
            dict(action.values) if action.type == "propose_values" else None
        )
        return AssistanceApiResponse(
            action=action,
            model_id=self._assistant.model_id,
            prompt_id=self._assistant.prompt_id,
            duration_ms=round(duration_ms, 3),
        )

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

        interaction = run.executor.current_interaction(run.response)
        interaction_id = _interaction_id(interaction)
        source = "manual"
        if run.latest_proposal is not None:
            source = "agent_proposal_review"
            run.trace.record_proposal_reviewed(
                interaction_id=interaction_id,
                proposed_values=run.latest_proposal,
                submitted_values=result,
            )
        run.trace.record_result_submitted(
            interaction_id=interaction_id,
            result=result,
            source=source,
        )

        run.response = run.executor.submit(run.response, result)
        run.latest_proposal = None
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
            assistant=create_environment_assistant(),
        )
    else:
        configured_service = run_service

    app = FastAPI(title="Journey executor prototype API", version="0.2.0")
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
        "/api/journey-runs/{run_id}/assistance",
        response_model=AssistanceApiResponse,
    )
    def request_assistance(
        run_id: str,
        request: AssistanceApiRequest,
    ) -> AssistanceApiResponse:
        """Propose values for the current interaction without advancing it.

        Args:
            run_id: Process-local run identifier.
            request: User message and earlier conversation context.

        Returns:
            Structured assistance action.

        Raises:
            HTTPException: If the run or assistant is unavailable or fails.
        """
        try:
            return configured_service.assist(
                run_id,
                message=request.message,
                conversation=request.conversation,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Journey run not found") from exc
        except _RunCompletedError as exc:
            raise HTTPException(
                status_code=409,
                detail="Journey run has already completed",
            ) from exc
        except _AssistantUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except InteractionAssistantError as exc:
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


def _interaction_id(interaction: ReadOnlyJsonObject | None) -> str | None:
    if interaction is None:
        return None
    raw_id = interaction.get("id")
    return raw_id if isinstance(raw_id, str) else None
