"""Thin HTTP adapter for browser-driven journey executor runs."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, TypeAlias

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from agents.src.evaluation import (
    ConversationFixtureRepository,
    ConversationFixtureSummary,
    LoadedConversationFixture,
)
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
    fixture_id: str | None = Field(default=None, min_length=1)
    assistance_enabled: bool = True


class SubmitResultRequest(BaseModel):
    """Result supplied for the current interaction."""

    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any]


class AddConversationMessageRequest(BaseModel):
    """New user-visible information added while a journey is active."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)


class AssistanceApiResponse(BaseModel):
    """Structured assistance generated for one current interaction."""

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
    fixture: ConversationFixtureSummary | None
    conversation: list[ConversationMessage]
    assistance: AssistanceApiResponse | None
    assistance_error: str | None


@dataclass
class _Run:
    journey_id: str
    executor: JourneyExecutor
    response: JsonObject
    trace: JsonlTraceRecorder
    assistance_enabled: bool = True
    loaded_fixture: LoadedConversationFixture | None = None
    source_conversation: list[ConversationMessage] = field(default_factory=list)
    journey_conversation: list[ConversationMessage] = field(default_factory=list)
    latest_assistance: AssistanceApiResponse | None = None
    latest_assistance_error: str | None = None
    latest_proposal: JsonObject | None = None

    def conversation(self) -> list[ConversationMessage]:
        """Return the complete user-visible conversation for this run.

        Returns:
            Fixed source messages followed by messages added during the journey.
        """
        return [*self.source_conversation, *self.journey_conversation]


class _RunCompletedError(RuntimeError):
    """Raised when a consumer tries to change an already completed run."""


class JourneyRunService:
    """Drive process-local runs for a browser or automated consumer.

    Args:
        trace_directory: Local directory used for raw JSONL traces.
        client_factory: Factory creating one traced journey client per run.
        assistant: Optional bounded assistant for the current interaction.
        fixture_repository: Version-controlled conversation fixture source.
    """

    def __init__(
        self,
        *,
        trace_directory: Path,
        client_factory: JourneyClientFactory,
        assistant: InteractionAssistant | None = None,
        fixture_repository: ConversationFixtureRepository | None = None,
    ) -> None:
        self._trace_directory = trace_directory
        self._client_factory = client_factory
        self._assistant = assistant
        self._fixture_repository = (
            fixture_repository or ConversationFixtureRepository()
        )
        self._runs: dict[str, _Run] = {}

    def list_fixtures(self) -> list[ConversationFixtureSummary]:
        """Return fixtures available to UI and automated consumers.

        Returns:
            Client-facing fixture metadata and source conversations.
        """
        return [loaded.summary() for loaded in self._fixture_repository.list()]

    def start(
        self,
        journey_id: str,
        *,
        fixture_id: str | None = None,
        assistance_enabled: bool = True,
        consumer: str = "agent_assisted_http_frontend",
    ) -> RunResponse:
        """Start a journey and generate suggestions from an optional fixture.

        Args:
            journey_id: Journey identifier advertised by the service catalogue.
            fixture_id: Optional version-controlled conversation fixture ID.
            assistance_enabled: Whether this run may invoke the interaction assistant.
            consumer: Trace label for the client driving the run.

        Returns:
            First interaction or terminal response, including any automatic proposal.

        Raises:
            KeyError: If the requested fixture does not exist.
            ValueError: If the fixture belongs to another journey.
            JourneyExecutorError: If the journey cannot be started or validated.
        """
        loaded_fixture = (
            self._fixture_repository.get(fixture_id) if fixture_id is not None else None
        )
        if (
            loaded_fixture is not None
            and loaded_fixture.fixture.journey_id != journey_id
        ):
            msg = (
                f"Conversation fixture {fixture_id!r} applies to "
                f"{loaded_fixture.fixture.journey_id!r}, not {journey_id!r}"
            )
            raise ValueError(msg)

        trace = JsonlTraceRecorder.create(
            self._trace_directory,
            journey_id=journey_id,
            consumer=consumer,
        )
        if loaded_fixture is not None:
            trace.record_fixture_loaded(
                fixture_id=loaded_fixture.fixture.id,
                fixture_version=loaded_fixture.fixture.version,
                fixture_sha256=loaded_fixture.sha256,
                conversation=[
                    message.model_dump(mode="json")
                    for message in loaded_fixture.fixture.conversation
                ],
            )

        executor = JourneyExecutor(self._client_factory(trace.record_exchange))
        response = executor.start(journey_id)
        run = _Run(
            journey_id=journey_id,
            executor=executor,
            response=response,
            trace=trace,
            assistance_enabled=assistance_enabled,
            loaded_fixture=loaded_fixture,
            source_conversation=(
                list(loaded_fixture.fixture.conversation)
                if loaded_fixture is not None
                else []
            ),
        )
        self._runs[trace.run_id] = run
        if executor.is_terminal(response):
            trace.record_finished(response)
        elif run.assistance_enabled:
            self._refresh_assistance(run)
        return self._view(trace.run_id, run)

    def add_message(self, run_id: str, content: str) -> RunResponse:
        """Append a user clarification and refresh suggestions.

        Args:
            run_id: Process-local run identifier.
            content: New user-visible message.

        Returns:
            Unchanged journey interaction with refreshed assistance.

        Raises:
            KeyError: If the run is not held by this process.
            _RunCompletedError: If the run has already reached terminal state.
        """
        run = self._runs[run_id]
        if run.executor.is_terminal(run.response):
            raise _RunCompletedError
        message = ConversationMessage(role="user", content=content)
        run.journey_conversation.append(message)
        interaction = run.executor.current_interaction(run.response)
        run.trace.record_user_message(
            interaction_id=_interaction_id(interaction),
            message=content,
        )
        self._refresh_assistance(run)
        return self._view(run_id, run)

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
            Next interaction or terminal response, with automatic assistance.

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
        self._clear_assistance(run)
        if run.executor.is_terminal(run.response):
            run.trace.record_finished(run.response)
        elif run.assistance_enabled:
            self._refresh_assistance(run)
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

    def _refresh_assistance(self, run: _Run) -> None:
        self._clear_assistance(run)
        if not run.assistance_enabled:
            return
        conversation = run.conversation()
        if not conversation:
            return

        interaction = run.executor.current_interaction(run.response)
        if interaction is None:  # pragma: no cover - caller checks terminality
            return
        if self._assistant is None:
            error = "Interaction assistant is not configured"
            run.latest_assistance_error = error
            run.trace.record_agent_failed(model_id=None, error=error)
            return

        request = AssistanceRequest(
            conversation=conversation,
            interaction=interaction,
        )
        conversation_payload = [
            item.model_dump(mode="json") for item in conversation
        ]
        run.trace.record_agent_invoked(
            model_id=self._assistant.model_id,
            prompt_id=self._assistant.prompt_id,
            interaction=interaction,
            conversation=conversation_payload,
        )
        started_at = perf_counter()
        try:
            action = validate_assistance_action(
                self._assistant.assist(request),
                interaction,
            )
        except InteractionAssistantError as exc:
            duration_ms = (perf_counter() - started_at) * 1000
            run.latest_assistance_error = str(exc)
            run.trace.record_agent_failed(
                model_id=self._assistant.model_id,
                error=str(exc),
                duration_ms=duration_ms,
            )
            return

        duration_ms = (perf_counter() - started_at) * 1000
        action_payload = action.model_dump(mode="json")
        run.trace.record_agent_responded(
            model_id=self._assistant.model_id,
            action=action_payload,
            duration_ms=duration_ms,
        )
        run.latest_assistance = AssistanceApiResponse(
            action=action,
            model_id=self._assistant.model_id,
            prompt_id=self._assistant.prompt_id,
            duration_ms=round(duration_ms, 3),
        )
        run.latest_proposal = (
            dict(action.values) if action.type == "propose_values" else None
        )

    @staticmethod
    def _clear_assistance(run: _Run) -> None:
        run.latest_assistance = None
        run.latest_assistance_error = None
        run.latest_proposal = None

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
            fixture=(
                run.loaded_fixture.summary()
                if run.loaded_fixture is not None
                else None
            ),
            conversation=run.conversation(),
            assistance=run.latest_assistance,
            assistance_error=run.latest_assistance_error,
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

    app = FastAPI(title="Journey executor prototype API", version="0.3.0")
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

    @app.get(
        "/api/conversation-fixtures",
        response_model=list[ConversationFixtureSummary],
    )
    def list_conversation_fixtures() -> list[ConversationFixtureSummary]:
        """Return version-controlled conversation fixtures.

        Returns:
            Fixtures available to demonstration and automated consumers.
        """
        return configured_service.list_fixtures()

    @app.post(
        "/api/journey-runs",
        response_model=RunResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def start_run(request: StartRunRequest) -> RunResponse:
        """Start one process-local journey run.

        Args:
            request: Journey and optional fixture selected by the consumer.

        Returns:
            First interaction with any automatic assistance.

        Raises:
            HTTPException: If the fixture or journey cannot be used.
        """
        try:
            return configured_service.start(
                request.journey_id,
                fixture_id=request.fixture_id,
                assistance_enabled=request.assistance_enabled,
                consumer=(
                    "agent_assisted_http_frontend"
                    if request.assistance_enabled
                    else "noagent_web_frontend"
                ),
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail="Conversation fixture not found",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except JourneyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JourneyExecutorError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post(
        "/api/journey-runs/{run_id}/messages",
        response_model=RunResponse,
    )
    def add_conversation_message(
        run_id: str,
        request: AddConversationMessageRequest,
    ) -> RunResponse:
        """Append user information and refresh current suggestions.

        Args:
            run_id: Process-local run identifier.
            request: New user-visible message.

        Returns:
            Current interaction with refreshed assistance.

        Raises:
            HTTPException: If the run is unavailable or complete.
        """
        try:
            return configured_service.add_message(run_id, request.content)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail="Journey run not found",
            ) from exc
        except _RunCompletedError as exc:
            raise HTTPException(
                status_code=409,
                detail="Journey run has already completed",
            ) from exc

    @app.post(
        "/api/journey-runs/{run_id}/results",
        response_model=RunResponse,
    )
    def submit_result(run_id: str, request: SubmitResultRequest) -> RunResponse:
        """Submit the current interaction result for a run.

        Args:
            run_id: Process-local run identifier.
            request: Reviewed values supplied by the consumer.

        Returns:
            Next interaction or terminal response.

        Raises:
            HTTPException: If the run cannot advance.
        """
        try:
            return configured_service.submit(run_id, request.result)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail="Journey run not found",
            ) from exc
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
            raise HTTPException(
                status_code=404,
                detail="Journey run not found",
            ) from exc
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
