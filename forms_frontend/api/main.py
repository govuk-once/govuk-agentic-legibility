"""Thin HTTP API bridging the GOV.UK Forms frontend to the existing
durable_poc agent and Temporal interpreter.

All journey progression goes through the existing Temporal workflow.
This API does NOT implement another journey state machine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import uuid
import ipaddress
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from temporalio.client import Client as TemporalClient
from temporalio.contrib.opentelemetry import TracingInterceptor

# durable_poc imports — available via PYTHONPATH=durable_poc
from agent import tools as tool_functions
from agent.agent import WorkflowAgent

from forms_frontend.api.sessions import (
    AcceptedAnswer,
    AutoAnsweredQuestion,
    FormSession,
    InteractionPolicy,
    SessionStore,
)
from forms_frontend.api.proposals import propose_answer
from forms_frontend.api.uploads import InvalidUpload, save_local_upload
from forms_frontend.api.tracing import (
    configure_telemetry, shutdown_telemetry, session_span, session_endpoint, fields, as_json,
)
from agent.agent import build_contextual_prompt

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

app = FastAPI(title="GOV.UK Forms Frontend API")


@app.on_event("startup")
async def _start_tracing() -> None:
    configure_telemetry()


@app.on_event("shutdown")
async def _shutdown() -> None:
    for agent in list(_agents.values()):
        await agent.close()
    if _http_client is not None:
        await _http_client.aclose()
    shutdown_telemetry()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Shared state ---

store = SessionStore()

_temporal_client: TemporalClient | None = None
_http_client: httpx.AsyncClient | None = None


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


async def get_temporal_client() -> TemporalClient:
    global _temporal_client
    if _temporal_client is None:
        addr = _env("TEMPORAL_ADDRESS", "localhost:7233")
        _temporal_client = await TemporalClient.connect(
            addr, interceptors=[TracingInterceptor()]
        )
    return _temporal_client


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient()
    return _http_client


async def _wait_for_workflow_progress(
    *,
    temporal: TemporalClient,
    workflow_id: str,
    previous_token: str | None,
    initial_state: dict[str, Any] | None = None,
    timeout_seconds: float = 1.5,
    poll_interval: float = 0.02,
) -> dict[str, Any]:
    """Return state after Temporal has consumed a submitted input.

    The update acknowledges receipt, not progression through the workflow loop.
    In particular, ``awaiting=None`` with RUNNING status is an *intermediate*
    state between the previous input and the next input (or completion). It is
    not evidence that the journey has finished or that a new question is ready.

    The interpreter remains authoritative: this helper only waits until its
    observable state changes (or the workflow completes).
    """

    state = initial_state or {}
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds

    while True:
        awaiting = state.get("awaiting") or {}
        token = awaiting.get("token")
        status = state.get("status")
        if status == "COMPLETED" or (token is not None and token != previous_token):
            return state

        if status not in (None, "RUNNING", "ADVANCING"):
            return state

        if loop.time() >= deadline:
            logger.warning(
                "Timed out waiting for workflow %s to advance beyond token %s",
                workflow_id,
                previous_token,
            )
            # Never return the *previous* awaiting input as a successful HTTP
            # submission. The browser can poll state, but must not resubmit.
            return {**state, "status": "ADVANCING", "awaiting": None}

        await asyncio.sleep(poll_interval)
        state = await tool_functions.get_workflow_state(
            workflow_id=workflow_id, temporal_client=temporal
        )


def _remember_completion(session: FormSession, state: dict[str, Any]) -> dict[str, Any]:
    """Latch an observed Temporal completion, not an inferred question count.

    Completed executions cannot return to an earlier input. Queries during
    completion (including queries racing with the final update) must not cause
    the browser to show the first or last question again.
    """
    if state.get("status") == "COMPLETED":
        session.terminal_state = {**state, "awaiting": None}
        session.pending_submission_token = None
        return session.terminal_state
    return state


async def _current_state(session: FormSession, temporal: TemporalClient) -> dict[str, Any]:
    """Mask consumed inputs and preserve a previously observed terminal state."""
    if session.terminal_state is not None:
        return session.terminal_state
    state = await tool_functions.get_workflow_state(
        workflow_id=session.temporal_workflow_id, temporal_client=temporal
    )
    state = _remember_completion(session, state)
    token = session.pending_submission_token
    if token is not None:
        awaiting = state.get("awaiting") or {}
        if (state.get("status") == "COMPLETED"
                or (awaiting.get("token") is not None and awaiting["token"] != token)
                or state.get("status") not in (None, "RUNNING", "ADVANCING")):
            session.pending_submission_token = None
        else:
            return {**state, "status": "ADVANCING", "awaiting": None}
    return state


def _is_mock_payment_input(awaiting: dict[str, Any] | None) -> bool:
    """Identify the compiler's ordinary Boolean input reserved for simulated payment."""
    return bool(
        awaiting
        and (awaiting.get("schema") or {}).get("kind") == "boolean"
        and ((awaiting.get("schema") or {}).get("presentation") or {}).get("answer_type")
        == "mock_payment"
    )


async def _submit_once(
    session: FormSession, temporal: TemporalClient, token: str, value: Any,
    *, auto_record: AutoAnsweredQuestion | None = None, source: str = "manual",
) -> tuple[dict[str, Any], bool]:
    """Token-guarded submission shared by manual, Confirm and Auto policies.

    An accepted update is never sent twice, even if a subsequent Temporal query
    still returns the previous input. The lock also serialises SSE and HTTP
    submissions for this (single-process POC) session.
    """
    actual_source = "auto" if auto_record is not None else source
    with session_span("forms.interpreter.submit", session, token=token,
                      requested_value=value, submission_source=actual_source,
                      proposal_explanation=auto_record.explanation if auto_record else None) as span:
        async with session.submission_lock:
            state = await _current_state(session, temporal)
            fields(span, state_before=state)
            if token in session.accepted_tokens:
                fields(span, outcome="duplicate", state_after=state)
                return state, False
            awaiting = state.get("awaiting") or {}
            fields(span, state_id=awaiting.get("state_id"), process_id=awaiting.get("process_id"),
                   question=awaiting.get("prompt"), schema=awaiting.get("schema"),
                   expected_token=awaiting.get("token"))
            if awaiting.get("token") != token:
                fields(span, outcome="stale_token")
                raise HTTPException(409, "This question is no longer awaiting an answer")
            if _is_mock_payment_input(awaiting):
                if auto_record is not None:
                    raise HTTPException(409, "Simulated payment requires an explicit user action")
                if session.review_before_submit and not session.review_confirmed:
                    raise HTTPException(409, "Confirm your answer review before simulated payment")
            if (awaiting.get("schema") or {}).get("kind") == "file_ref":
                _check_file_submission(session, token, value)

            # The Temporal update validator rejects invalid values and stale tokens;
            # record acceptance *only after* the update returns successfully.
            with session_span("forms.temporal.update", session, token=token,
                              submitted_value=value, state_id=awaiting.get("state_id")) as update_span:
                initial = await tool_functions.submit_input(
                    workflow_id=session.temporal_workflow_id,
                    token=token, value=value, temporal_client=temporal,
                )
                fields(update_span, accepted=True, temporal_response=initial)
            session.accepted_tokens.add(token)
            # Record accepted automatic answers immediately, not after polling.
            # A browser closing the SSE stream during the next-state wait must
            # not silently lose a submission from the cumulative summary.
            if auto_record is not None:
                session.auto_answered.append(auto_record)
            # Capture the *actual accepted* value and the question it belongs to.
            # This history is read-only until a review edit has been validated by
            # replaying it through a fresh instance of the SAME Temporal interpreter.
            if not _is_mock_payment_input(awaiting):
                session.answer_history.append(AcceptedAnswer(
                    token=token,
                    state_id=awaiting.get("state_id") or "",
                    question_text=awaiting.get("prompt", ""),
                    schema=awaiting.get("schema") or {},
                    presentation=_lookup_state_presentation(
                        session.definition, awaiting.get("state_id")
                    ) or (awaiting.get("schema") or {}).get("presentation"),
                    value=value,
                    source="auto" if auto_record is not None else source,
                    explanation=auto_record.explanation if auto_record else "",
                ))
            # Store the mock outcome in Temporal, but do not include this step
            # as a reviewable question or replay it during final review.
            session.review_replay_needs_input = False
            session.pending_submission_token = token
            with session_span("forms.temporal.progress", session, previous_token=token) as progress_span:
                state = await _wait_for_workflow_progress(
                    temporal=temporal,
                    workflow_id=session.temporal_workflow_id,
                    previous_token=token, initial_state=initial,
                )
                fields(progress_span, returned_state=state)
            state = _remember_completion(session, state)
            if state["status"] != "ADVANCING":
                session.pending_submission_token = None
            fields(span, outcome="accepted", submitted=True, state_after=state,
                   next_state_id=(state.get("awaiting") or {}).get("state_id"),
                   next_token=(state.get("awaiting") or {}).get("token"))
            return state, True


def _workflow_server_url() -> str:
    return _env("WORKFLOW_SERVER_URL", "http://localhost:8080")


def _task_queue() -> str:
    return _env("TEMPORAL_TASK_QUEUE", "sfsm-queue")


def _to_strands_messages(conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert simple {role, content} messages to Strands Message format.

    Strands expects: {"role": "user", "content": [{"text": "..."}]}
    Fixtures provide: {"role": "user", "content": "..."}
    """
    messages = []
    for msg in conversation:
        content = msg.get("content", "")
        if isinstance(content, str):
            content = [{"text": content}]
        messages.append({"role": msg["role"], "content": content})
    return messages


def _create_agent(conversation_history: list[dict] | None = None) -> WorkflowAgent:
    strands_messages = _to_strands_messages(conversation_history) if conversation_history else None
    return WorkflowAgent(
        workflow_server_url=_workflow_server_url(),
        model_id=_env("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6"),
        region_name=_env("AWS_REGION", "eu-west-2"),
        temporal_address=_env("TEMPORAL_ADDRESS", "localhost:7233"),
        task_queue=_task_queue(),
        conversation_history=strands_messages,
    )


# Agents keyed by session_id
_agents: dict[str, WorkflowAgent] = {}


def _get_or_create_agent(session: FormSession) -> WorkflowAgent:
    if session.session_id not in _agents:
        _agents[session.session_id] = _create_agent(session.conversation_history)
    return _agents[session.session_id]


def _lookup_definition_state(
    definition: dict[str, Any], process_id: str | None, state_id: str | None
) -> dict[str, Any] | None:
    """Look up one SFSM state without interpreting or advancing the journey."""
    if not process_id or not state_id:
        return None
    process = definition.get("processes", {}).get(process_id) or {}
    state = (process.get("states") or {}).get(state_id)
    return state if isinstance(state, dict) else None


async def _refresh_review_readiness(
    session: FormSession, temporal: TemporalClient, state: dict[str, Any]
) -> bool:
    """Latch review at the payment input or a terminal EndState.

    There is a small but observable gap after the final input update: the
    interpreter has consumed the answer and reached its terminal EndState while
    Temporal can still describe the execution as RUNNING.  Waiting only for the
    transport status caused the review UI to sit forever on an ``ADVANCING``
    placeholder in live runs.

    This does *not* infer completion from question counts. Review begins at
    the generated payment input (before any payment simulation), or when the
    authoritative SFSM interpreter reaches an actual EndState.
    """
    if not session.review_before_submit or session.review_confirmed:
        return False
    if session.review_ready:
        return True
    if _is_mock_payment_input(state.get("awaiting")):
        # Payment is deliberately *after* answer review. The authoritative
        # Temporal input marks the boundary; no payment has occurred yet.
        session.review_ready = True
        with session_span("forms.review.ready", session, state_id="end_form",
                          answer_history=[_answer_data(item) for item in session.answer_history]):
            pass
        return True
    if state.get("awaiting"):
        return False

    try:
        handle = temporal.get_workflow_handle(session.temporal_workflow_id)
        info = await handle.query("current_state_info")
    except Exception:
        # Some test doubles/older runtimes do not expose this query.  The normal
        # COMPLETED path below remains valid, so failure here is non-fatal.
        return False

    if not isinstance(info, dict) or info.get("state_type") != "EndState":
        return False
    definition_state = _lookup_definition_state(
        session.definition, info.get("process_id"), info.get("state_id")
    )
    if not definition_state or definition_state.get("type") != "end":
        return False

    outcome = definition_state.get("outcome")
    session.review_terminal_outcome = outcome if isinstance(outcome, str) else None
    # Exit pages are terminal redirects/messages, not forms awaiting approval.
    if outcome == "exit_page":
        return False
    session.review_ready = True
    with session_span("forms.review.ready", session, terminal_info=info,
                      answer_history=[_answer_data(item) for item in session.answer_history]):
        pass
    return True


def _lookup_state_presentation(
    definition: dict[str, Any], state_id: str | None
) -> dict[str, Any] | None:
    """Find the presentation metadata for a given state_id in the definition."""
    if not state_id or not definition:
        return None
    for proc in definition.get("processes", {}).values():
        states = proc.get("states", {})
        state = states.get(state_id)
        if state and state.get("type") == "input":
            return state.get("schema", {}).get("presentation")
    return None


def _review_is_safe(definition: dict[str, Any]) -> bool:
    """Do not replay journeys with non-idempotent actions or sub-processes.

    Compiled Forms in this POC use input/choice/output/end and pure append
    assignments for repeatable questions. Review remains unavailable for
    arbitrary assignments and future departmental actions need an
    explicit pre-submission gate rather than replaying side effects.
    """
    return all(
        state.get("type") in {"input", "choice", "end"}
        or (state.get("type") == "assign" and state.get("set")
            and all(isinstance(expr, dict) and expr.get("op") == "append"
                    for expr in state["set"].values()))
        or (state.get("type") == "output" and state.get("channel") == "transcript")
        for proc in definition.get("processes", {}).values()
        for state in proc.get("states", {}).values()
    ) and bool(definition.get("processes"))


def _answer_data(entry: AcceptedAnswer) -> dict[str, Any]:
    return {
        "state_id": entry.state_id,
        "question_text": entry.question_text,
        "value": entry.value,
        "schema": entry.schema,
        "presentation": entry.presentation,
        "source": entry.source,
    }


# =====================================================================
# Request/Response models
# =====================================================================


class StartSessionRequest(BaseModel):
    form_id: str | int
    policy: str = "manual"
    review_before_submit: bool = False
    fixture_id: str | None = None


class StartSessionResponse(BaseModel):
    session_id: str
    form_id: str
    form_name: str
    temporal_workflow_id: str
    policy: str
    review_before_submit: bool = False
    fixture_id: str | None = None
    conversation_messages: int = 0


class SubmitAnswerRequest(BaseModel):
    token: str
    value: Any


class MockFileRequest(BaseModel):
    """Metadata only: the browser never sends file bytes in preview mode."""

    bytes: int = Field(gt=0, le=2**53 - 1)
    content_type: str = Field(default="application/octet-stream", max_length=200)


class ChatRequest(BaseModel):
    message: str


class PolicyRequest(BaseModel):
    policy: str
    review_before_submit: bool | None = None


class ReviewAmendRequest(BaseModel):
    index: int
    state_id: str
    value: Any
    revision: int


# =====================================================================
# Endpoints
# =====================================================================


def _load_fixtures() -> list[dict[str, Any]]:
    """Load all conversation fixtures from the fixtures directory."""
    fixtures = []
    if FIXTURES_DIR.is_dir():
        for path in sorted(FIXTURES_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                fixtures.append({
                    "id": data["id"],
                    "title": data.get("title", path.stem),
                    "description": data.get("description", ""),
                    "form_id": data.get("form_id"),
                    "message_count": len(data.get("conversation", [])),
                })
            except (json.JSONDecodeError, KeyError):
                logger.warning("Skipping invalid fixture: %s", path)
    return fixtures


def _load_fixture(fixture_id: str) -> dict[str, Any] | None:
    """Load a single fixture by id."""
    if FIXTURES_DIR.is_dir():
        for path in FIXTURES_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                if data.get("id") == fixture_id:
                    return data
            except (json.JSONDecodeError, KeyError):
                continue
    return None


@app.get("/api/fixtures")
async def list_fixtures() -> list[dict[str, Any]]:
    """List available conversation fixtures."""
    return _load_fixtures()


@app.get("/api/fixtures/{fixture_id}")
async def get_fixture(fixture_id: str) -> dict[str, Any]:
    """Get a single fixture by id."""
    fixture = _load_fixture(fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return fixture


@app.get("/api/forms")
async def list_forms() -> list[dict[str, Any]]:
    """List available GOV.UK Forms from the workflow definition server."""
    http = await get_http_client()
    workflows = await tool_functions.list_available_workflows(
        http_client=http, base_url=_workflow_server_url()
    )
    return workflows


@app.get("/api/forms/{form_id}")
async def get_form(form_id: str) -> dict[str, Any]:
    """Get a form definition with its metadata."""
    http = await get_http_client()
    definition = await tool_functions.get_workflow_definition(
        workflow_id=form_id, http_client=http, base_url=_workflow_server_url()
    )
    return {
        "form_id": form_id,
        "definition": definition,
        "metadata": definition.get("defaults", {}).get("forms", {}),
    }


@app.post("/api/sessions", response_model=StartSessionResponse)
async def start_session(req: StartSessionRequest) -> StartSessionResponse:
    """Start a new form session: fetches definition, starts Temporal workflow."""
    with session_span("forms.session.start", form_id=str(req.form_id), request=req.model_dump()) as span:
        http = await get_http_client()
        temporal = await get_temporal_client()

        definition = await tool_functions.get_workflow_definition(
            workflow_id=req.form_id, http_client=http, base_url=_workflow_server_url()
        )

        if req.review_before_submit and not _review_is_safe(definition):
            raise HTTPException(422, "Final review is not yet supported for forms with service actions")

        temporal_workflow_id = await tool_functions.start_workflow(
            workflow_id=req.form_id,
            http_client=http,
            base_url=_workflow_server_url(),
            temporal_client=temporal,
            task_queue=_task_queue(),
        )

        form_metadata = definition.get("defaults", {}).get("forms", {})
        policy = InteractionPolicy(req.policy) if req.policy in InteractionPolicy.__members__.values() else InteractionPolicy.MANUAL

        conversation_history: list[dict[str, Any]] = []
        if req.fixture_id:
            fixture = _load_fixture(req.fixture_id)
            if fixture:
                conversation_history = fixture.get("conversation", [])
                logger.info(
                    "Loaded fixture %r with %d messages",
                    req.fixture_id,
                    len(conversation_history),
                )
            else:
                logger.warning("Fixture %r not found, starting with empty history", req.fixture_id)

        session = store.create(
            form_id=str(req.form_id),
            temporal_workflow_id=temporal_workflow_id,
            form_metadata=form_metadata,
            definition=definition,
            policy=policy,
            review_before_submit=req.review_before_submit,
            conversation_history=conversation_history,
        )

        fields(span, event_seq=next(session.trace_sequence),
               session_id=session.session_id, workflow_id=temporal_workflow_id,
               policy=session.policy.value, form_metadata=form_metadata,
               definition=definition, initial_conversation=conversation_history,
               review_before_submit=session.review_before_submit)
        span.set_attribute("session_id", session.session_id)
        span.set_attribute("temporalWorkflowID", temporal_workflow_id)
        return StartSessionResponse(
            session_id=session.session_id,
            form_id=session.form_id,
            form_name=form_metadata.get("name", f"Form {req.form_id}"),
            temporal_workflow_id=temporal_workflow_id,
            policy=session.policy.value,
            review_before_submit=session.review_before_submit,
            fixture_id=req.fixture_id,
            conversation_messages=len(conversation_history),
        )


@app.get("/api/sessions/{session_id}/state")
@session_endpoint("forms.state.read")
async def get_session_state(session_id: str) -> dict[str, Any]:
    """Get the current workflow state including awaiting input and presentation metadata."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    temporal = await get_temporal_client()
    state = await _current_state(session, temporal)

    awaiting = state.get("awaiting")
    presentation = None
    if awaiting:
        state_id = awaiting.get("state_id")
        presentation = _lookup_state_presentation(session.definition, state_id)
        if not presentation:
            presentation = awaiting.get("schema", {}).get("presentation")

    # Review is a journey-level state, not a Temporal transport status.  The
    # interpreter can be sitting on its terminal EndState for a short period
    # before Temporal reports the execution as CLOSED.  Detect that state
    # directly so the browser can render Check your answers immediately.
    # A simulated payment InputState is also an explicit pre-payment review gate.
    await _refresh_review_readiness(session, temporal, state)

    if state.get("status") == "COMPLETED" and session.terminal_result is None:
        session.terminal_result = await _terminal_result(
            temporal, session.temporal_workflow_id, state
        )
    result = session.terminal_result if state.get("status") == "COMPLETED" else None
    if (state.get("status") == "COMPLETED"
            and session.review_before_submit
            and not session.review_confirmed
            and (result or {}).get("outcome") != "exit_page"):
        # Preserve the old completed-execution path for runtimes where the
        # EndState query is no longer available after closure.
        session.review_ready = True
        if isinstance((result or {}).get("outcome"), str):
            session.review_terminal_outcome = result["outcome"]
    review_required = (session.review_before_submit and not session.review_confirmed
                       and session.review_ready and (result or {}).get("outcome") != "exit_page")

    return {
        "session_id": session_id,
        "workflow_id": session.temporal_workflow_id,
        "status": state.get("status", "RUNNING"),
        "awaiting": awaiting,
        "presentation": presentation,
        "form_metadata": session.form_metadata,
        "policy": session.policy.value,
        "upload_mode": "local" if os.getenv("FORMS_ENABLE_DEV_UPLOADS") == "1" else "mock",
        "answered_count": len(session.accepted_tokens),
        "review_before_submit": session.review_before_submit,
        "review_required": review_required,
        "review_confirmed": session.review_confirmed,
        "review_ready": session.review_ready,
        "review_revision": session.review_revision,
        "review_replay_needs_input": session.review_replay_needs_input,
        "answer_history": [_answer_data(item) for item in session.answer_history],
        "auto_answered": [
            {
                "state_id": q.state_id,
                "question_text": q.question_text,
                "submitted_value": q.submitted_value,
                "explanation": q.explanation,
            }
            for q in session.auto_answered
        ],
        "pending_proposal": session.pending_proposal,
        "transcript": state.get("transcript") or [],
        "result": result,
    }


async def _terminal_result(temporal: TemporalClient, workflow_id: str, state: dict) -> dict | None:
    if state.get("status") != "COMPLETED":
        return None
    try:
        result = await temporal.get_workflow_handle(workflow_id).result()
        return result if isinstance(result, dict) else None
    except Exception:
        logger.exception("Unable to read completion outcome for %s", workflow_id)
        return None


def _check_file_submission(session: FormSession, token: str, value: Any) -> None:
    if value is None:
        return  # Temporal enforces whether the file_ref is optional.
    if not isinstance(value, dict):
        raise HTTPException(422, "Upload a file before submitting a file question")
    ref = value.get("ref")
    is_mock = value.get("mock") is True
    references = session.mock_files if is_mock else session.uploaded_files
    recorded = references.get(ref) if isinstance(ref, str) else None
    if recorded != (token, value.get("bytes"), value.get("content_type")):
        raise HTTPException(422, "File reference was not issued for this question")


@app.post("/api/sessions/{session_id}/files/mock")
@session_endpoint("forms.file.mock")
async def mock_file(session_id: str, request: MockFileRequest, token: str) -> dict[str, object]:
    """Create a token-bound preview reference without receiving or storing bytes.

    Preview references are conspicuously marked as NOT uploaded. They are for
    running the SFSM journey only, not for departmental form submission.
    """
    if os.getenv("FORMS_ENABLE_DEV_UPLOADS") == "1":
        raise HTTPException(409, "Mock uploads disabled while local uploads are enabled")
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    temporal = await get_temporal_client()
    state = await tool_functions.get_workflow_state(
        workflow_id=session.temporal_workflow_id, temporal_client=temporal)
    awaiting = state.get("awaiting") or {}
    if awaiting.get("token") != token or (awaiting.get("schema") or {}).get("kind") != "file_ref":
        raise HTTPException(409, "Workflow is not awaiting this file input")
    ref = f"mock://{session.session_id}/{uuid.uuid4().hex}"
    content_type = request.content_type or "application/octet-stream"
    session.mock_files[ref] = (token, request.bytes, content_type)
    return {"ref": ref, "bytes": request.bytes, "content_type": content_type, "mock": True}


@app.post("/api/sessions/{session_id}/files")
@session_endpoint("forms.file.upload")
async def upload_file(session_id: str, request: Request, token: str) -> dict[str, object]:
    """Store real synthetic bytes locally and return a file_ref for Temporal."""
    if os.getenv("FORMS_ENABLE_DEV_UPLOADS") != "1":
        raise HTTPException(403, "Local development uploads are disabled")
    host = request.client.host if request.client else ""
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "testclient"
    if not loopback:
        raise HTTPException(403, "Local uploads are available only from loopback")
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    temporal = await get_temporal_client()
    state = await tool_functions.get_workflow_state(
        workflow_id=session.temporal_workflow_id, temporal_client=temporal)
    awaiting = state.get("awaiting") or {}
    if awaiting.get("token") != token or (awaiting.get("schema") or {}).get("kind") != "file_ref":
        raise HTTPException(409, "Workflow is not awaiting this file input")
    directory = Path(os.getenv("FORMS_UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "forms-synthetic-uploads")))
    try:
        value = await save_local_upload(chunks=request.stream(), directory=directory,
                                        session_id=session.session_id,
                                        content_type=request.headers.get("content-type", "application/octet-stream"))
    except InvalidUpload as exc:
        raise HTTPException(413, str(exc)) from exc
    session.uploaded_files[str(value["ref"])] = (token, int(value["bytes"]), str(value["content_type"]))
    return value


@app.post("/api/sessions/{session_id}/submit")
@session_endpoint("forms.user_turn")
async def submit_answer(session_id: str, req: SubmitAnswerRequest) -> dict[str, Any]:
    """Submit a manual answer to the current question via Temporal."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    temporal = await get_temporal_client()
    try:
        new_state, _ = await _submit_once(session, temporal, req.token, req.value)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if session.pending_proposal is not None:
        with session_span("forms.proposal.decision", session,
                          proposal=session.pending_proposal, submitted_value=req.value,
                          action="manual_override", accepted=True):
            pass
    session.pending_proposal = None

    awaiting = new_state.get("awaiting")
    presentation = None
    if awaiting:
        state_id = awaiting.get("state_id")
        presentation = _lookup_state_presentation(session.definition, state_id)
        if not presentation:
            presentation = awaiting.get("schema", {}).get("presentation")

    return {
        "session_id": session_id,
        "status": new_state.get("status", "RUNNING"),
        "awaiting": awaiting,
        "presentation": presentation,
        "form_metadata": session.form_metadata,
    }


@app.post("/api/sessions/{session_id}/chat")
@session_endpoint("forms.user_turn")
async def chat(session_id: str, req: ChatRequest) -> dict[str, Any]:
    """Send a conversational message to the agent."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    temporal = await get_temporal_client()
    state = await tool_functions.get_workflow_state(
        workflow_id=session.temporal_workflow_id, temporal_client=temporal
    )
    if _is_mock_payment_input(state.get("awaiting")):
        # The chat agent has direct Temporal tools: do not let conversation
        # bypass the user's explicit choice on the simulated payment page.
        return {"response": "This payment page is only a simulation. No money will be taken. "
                            "Choose a button on the simulated payment page to continue or cancel.",
                "state": state}

    agent = _get_or_create_agent(session)
    # WorkflowAgent already emits agent.respond and tool.* spans. Record the
    # exact material passed into it and its full result at this API boundary.
    with session_span("forms.agent.exchange", session, user_message=req.message,
                      workflow_context=state, context_prompt=build_contextual_prompt(req.message, context=state),
                      system_prompt=agent._system_prompt,
                      conversation_before=session.conversation_history,
                      strands_messages_before=agent._agent.messages) as agent_span:
        session.conversation_history.append({"role": "user", "content": req.message})
        try:
            response = await agent.respond(req.message, context=state)
        except Exception as e:
            logger.exception("Agent respond failed for session %s", session_id)
            raise HTTPException(status_code=502, detail=f"Agent error: {e}") from e
        session.conversation_history.append({"role": "assistant", "content": response})
        fields(agent_span, response=response, conversation_after=session.conversation_history,
               strands_messages_after=agent._agent.messages,
               agent_session_state=agent.session_state)

        updated_state = await tool_functions.get_workflow_state(
            workflow_id=session.temporal_workflow_id, temporal_client=temporal
        )
        # A free-form chat can answer a question without submitting to Temporal.
        fields(agent_span, workflow_state_after=updated_state)

    return {
        "response": response,
        "state": updated_state,
    }


@app.post("/api/sessions/{session_id}/propose")
@session_endpoint("forms.proposal.request")
async def propose(session_id: str) -> dict[str, Any]:
    """Ask the agent to propose an answer for the current question.

    In MANUAL policy, proposals are not generated.
    In CONFIRM policy, the proposal is returned for user confirmation.
    In AUTO policy, the proposal is submitted automatically if confident.
    """
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.policy == InteractionPolicy.MANUAL:
        return {"has_answer": False, "value": None, "explanation": "Manual mode — no proposals"}

    temporal = await get_temporal_client()
    state = await tool_functions.get_workflow_state(
        workflow_id=session.temporal_workflow_id, temporal_client=temporal
    )

    awaiting = state.get("awaiting")
    if not awaiting:
        return {"has_answer": False, "value": None, "explanation": "No question pending"}
    if _is_mock_payment_input(awaiting):
        return {"has_answer": False, "value": None,
                "explanation": "Simulated payment must be chosen by the user"}

    proposal = await propose_answer(
        conversation_history=session.conversation_history,
        awaiting=awaiting, session=session,
    )
    logger.info("Proposal result for session %s: %s", session_id, proposal)

    if not proposal.get("has_answer"):
        with session_span("forms.proposal.decision", session, proposal=proposal,
                          state_id=awaiting.get("state_id"), action="not_usable"):
            session.pending_proposal = None
        return proposal

    if session.policy == InteractionPolicy.CONFIRM:
        with session_span("forms.proposal.decision", session, proposal=proposal,
                          state_id=awaiting.get("state_id"), action="presented_for_confirmation"):
            pass
        session.pending_proposal = {
            "token": awaiting["token"],
            "state_id": awaiting.get("state_id"),
            "question_text": awaiting.get("prompt", ""),
            **proposal,
        }
        return {**proposal, "requires_confirmation": True}

    if session.policy == InteractionPolicy.AUTO:
        return await _auto_progress(session, state, proposal, temporal)

    return proposal


async def _auto_progress(
    session: FormSession,
    initial_state: dict[str, Any],
    initial_proposal: dict[str, Any],
    temporal: TemporalClient,
    max_steps: int = 20,
) -> dict[str, Any]:
    """Automatically submit answers while the agent is confident.

    Stops when the agent lacks information, validation fails,
    the journey completes, or the step limit is reached.
    """
    state = initial_state
    proposal = initial_proposal
    steps_taken = 0

    while proposal.get("has_answer") and steps_taken < max_steps:
        awaiting = state.get("awaiting")
        if not awaiting or _is_mock_payment_input(awaiting):
            break

        token = awaiting["token"]
        value = proposal["value"]
        if (awaiting.get("schema") or {}).get("kind") == "file_ref":
            break  # An LLM cannot generate a real upload reference.

        try:
            state, submitted = await _submit_once(
                session, temporal, token, value,
                auto_record=AutoAnsweredQuestion(
                    state_id=awaiting.get("state_id", ""),
                    question_text=awaiting.get("prompt", ""),
                    submitted_value=value,
                    explanation=proposal.get("explanation", ""),
                ),
            )
        except Exception as exc:
            with session_span("forms.proposal.decision", session, proposal=proposal,
                              state_id=awaiting.get("state_id"), action="submission_failed",
                              error=str(exc)):
                pass
            logger.exception("Auto-progress submission failed")
            break
        with session_span("forms.proposal.decision", session, proposal=proposal,
                          state_id=awaiting.get("state_id"), token=token,
                          action="auto_submitted" if submitted else "duplicate_not_submitted",
                          returned_state=state):
            pass

        if submitted:
            steps_taken += 1

        if state.get("status") == "ADVANCING":
            break

        awaiting = state.get("awaiting")
        if not awaiting or _is_mock_payment_input(awaiting):
            break

        proposal = await propose_answer(
            conversation_history=session.conversation_history,
            awaiting=awaiting, session=session,
        )
        if not proposal.get("has_answer"):
            with session_span("forms.proposal.decision", session, proposal=proposal,
                              state_id=awaiting.get("state_id"), action="not_usable"):
                pass

    session.pending_proposal = None

    awaiting = state.get("awaiting")
    presentation = None
    if awaiting:
        state_id = awaiting.get("state_id")
        presentation = _lookup_state_presentation(session.definition, state_id)
        if not presentation:
            presentation = awaiting.get("schema", {}).get("presentation")

    return {
        "has_answer": False,
        "value": None,
        "explanation": f"Auto-progressed {steps_taken} step(s)",
        "steps_taken": steps_taken,
        "current_state": {
            "status": state.get("status", "RUNNING"),
            "awaiting": awaiting,
            "presentation": presentation,
        },
        "auto_answered": [
            {
                "state_id": q.state_id,
                "question_text": q.question_text,
                "submitted_value": q.submitted_value,
                "explanation": q.explanation,
            }
            for q in session.auto_answered
        ],
    }


@app.get("/api/sessions/{session_id}/auto-progress")
@session_endpoint("forms.auto.request")
async def auto_progress_stream(session_id: str, request: Request) -> EventSourceResponse:
    """Stream auto-progress events as the agent steps through questions.

    Each SSE event is a JSON object with type: "step", "waiting", or "done".
    """
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.policy != InteractionPolicy.AUTO:
        raise HTTPException(status_code=409, detail="Automatic mode is not enabled")

    async def _event_generator_impl():
        temporal = await get_temporal_client()
        state = await _current_state(session, temporal)

        # Count total input states in the definition for progress denominator
        total_questions = 0
        for proc in session.definition.get("processes", {}).values():
            for s in proc.get("states", {}).values():
                if (s.get("type") == "input" and
                        (s.get("schema", {}).get("presentation") or {}).get("answer_type") != "mock_payment"):
                    total_questions += 1

        steps_taken = len(session.auto_answered)
        steps_this_run = 0
        max_steps = 20

        while steps_this_run < max_steps:
            if await request.is_disconnected():
                break
            if session.policy != InteractionPolicy.AUTO:
                with session_span("forms.proposal.decision", session,
                                  proposal=proposal, current_question=awaiting,
                                  action="policy_changed_not_submitted"):
                    pass
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "type": "done", "reason": "policy_changed",
                        "steps_taken": steps_taken,
                        "total_questions": total_questions,
                    }),
                }
                return

            awaiting = state.get("awaiting")
            if not awaiting:
                # RUNNING without an input is *not* completion. It is the
                # transition between a consumed input and the next state.
                reason = "complete" if state.get("status") == "COMPLETED" else "pending"
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "type": "done",
                        "reason": reason,
                        "steps_taken": steps_taken,
                        "total_questions": total_questions,
                    }),
                }
                return

            if _is_mock_payment_input(awaiting):
                yield {"event": "done", "data": json.dumps({
                    "type": "done", "reason": "needs_input", "steps_taken": steps_taken,
                    "answered_count": len(session.accepted_tokens),
                    "total_questions": total_questions})}
                return

            yield {
                "event": "waiting",
                "data": json.dumps({
                    "type": "waiting",
                    "question": awaiting.get("prompt", ""),
                    "step": steps_taken + 1,
                    "answered_count": len(session.accepted_tokens),
                    "total_questions": total_questions,
                }),
            }

            proposal = await propose_answer(
                conversation_history=session.conversation_history,
                awaiting=awaiting, session=session,
            )

            if not proposal.get("has_answer"):
                with session_span("forms.proposal.decision", session,
                                  proposal=proposal, current_question=awaiting,
                                  action="needs_input"):
                    pass
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "type": "done",
                        "reason": "needs_input",
                        "question": awaiting.get("prompt", ""),
                        "steps_taken": steps_taken,
                        "answered_count": len(session.accepted_tokens),
                        "total_questions": total_questions,
                    }),
                }
                return

            # A policy switch during the LLM call must not submit its result.
            if session.policy != InteractionPolicy.AUTO:
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "type": "done", "reason": "policy_changed",
                        "steps_taken": steps_taken,
                        "total_questions": total_questions,
                    }),
                }
                return

            token = awaiting["token"]
            value = proposal["value"]
            if (awaiting.get("schema") or {}).get("kind") == "file_ref":
                yield {"event": "done", "data": json.dumps({
                    "type": "done", "reason": "needs_upload", "steps_taken": steps_taken,
                    "total_questions": total_questions})}
                return

            try:
                state, submitted = await _submit_once(
                    session, temporal, token, value,
                    auto_record=AutoAnsweredQuestion(
                        state_id=awaiting.get("state_id", ""),
                        question_text=awaiting.get("prompt", ""),
                        submitted_value=value,
                        explanation=proposal.get("explanation", ""),
                    ),
                )
            except Exception as exc:
                with session_span("forms.proposal.decision", session,
                                  proposal=proposal, current_question=awaiting,
                                  action="submission_failed", error_message=str(exc)):
                    pass
                logger.exception("Auto-progress submission failed at step %d", steps_taken)
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "type": "done",
                        "reason": "error",
                        "steps_taken": steps_taken,
                        "total_questions": total_questions,
                    }),
                }
                return

            with session_span("forms.proposal.decision", session,
                              proposal=proposal, current_question=awaiting,
                              action="auto_submitted" if submitted else "duplicate",
                              submitted_value=value, returned_state=state):
                pass
            if submitted:
                steps_taken += 1
                steps_this_run += 1

                yield {
                    "event": "step",
                    "data": json.dumps({
                        "type": "step",
                        "question": awaiting.get("prompt", ""),
                        "value": str(value),
                        "explanation": proposal.get("explanation", ""),
                        "steps_taken": steps_taken,
                        "answered_count": len(session.accepted_tokens),
                        "total_questions": total_questions,
                    }),
                }

            # The event stream must not propose an answer to a transiently
            # empty or old awaiting state. The browser polls the accepted
            # submission and starts a new pass when the next token is ready.
            if state.get("status") == "ADVANCING":
                yield {"event": "done", "data": json.dumps({
                    "type": "done", "reason": "pending", "steps_taken": steps_taken,
                    "answered_count": len(session.accepted_tokens),
                    "total_questions": total_questions})}
                return

        yield {
            "event": "done",
            "data": json.dumps({
                "type": "done",
                "reason": "max_steps",
                "steps_taken": steps_taken,
                "total_questions": total_questions,
            }),
        }

    async def event_generator():
        with session_span("forms.auto.stream", session,
                          conversation=session.conversation_history):
            async for event in _event_generator_impl():
                yield event

    return EventSourceResponse(event_generator())


@app.post("/api/sessions/{session_id}/confirm-proposal")
@session_endpoint("forms.proposal.accept")
async def confirm_proposal(session_id: str) -> dict[str, Any]:
    """Confirm and submit the pending answer proposal."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.pending_proposal:
        raise HTTPException(status_code=400, detail="No pending proposal")

    temporal = await get_temporal_client()
    proposal = session.pending_proposal
    token = proposal["token"]
    value = proposal["value"]

    try:
        new_state, submitted = await _submit_once(
            session, temporal, token, value, source="confirm"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Confirmed proposals require user authorisation and are not *automatic*
    # answers. They do contribute to accepted journey progress, via the token.
    with session_span("forms.proposal.decision", session, proposal=proposal,
                      action="confirmed" if submitted else "duplicate_confirmation",
                      submitted_value=value, returned_state=new_state):
        pass
    session.pending_proposal = None

    awaiting = new_state.get("awaiting")
    presentation = None
    if awaiting:
        state_id = awaiting.get("state_id")
        presentation = _lookup_state_presentation(session.definition, state_id)
        if not presentation:
            presentation = awaiting.get("schema", {}).get("presentation")

    return {
        "session_id": session_id,
        "status": new_state.get("status", "RUNNING"),
        "awaiting": awaiting,
        "presentation": presentation,
    }


@app.post("/api/sessions/{session_id}/reject-proposal")
@session_endpoint("forms.proposal.reject")
async def reject_proposal(session_id: str) -> dict[str, Any]:
    """Reject the pending proposal — user will answer manually."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    with session_span("forms.proposal.decision", session,
                      proposal=session.pending_proposal, action="rejected"):
        session.pending_proposal = None
    return {"status": "rejected"}


@app.put("/api/sessions/{session_id}/policy")
@session_endpoint("forms.policy.change")
async def set_policy(session_id: str, req: PolicyRequest) -> dict[str, Any]:
    """Change answer policy and optional pre-submission review independently."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    try:
        new_policy = InteractionPolicy(req.policy)
    except ValueError:
        raise HTTPException(400, f"Invalid policy. Must be one of: {[p.value for p in InteractionPolicy]}")
    if req.review_before_submit is not None:
        if session.review_confirmed:
            raise HTTPException(409, "This form has already been finalised")
        if req.review_before_submit and not _review_is_safe(session.definition):
            raise HTTPException(422, "Final review is not yet supported for forms with service actions")
        session.review_before_submit = req.review_before_submit
    old_policy = session.policy.value
    session.policy = new_policy
    with session_span("forms.policy.changed", session, previous_policy=old_policy,
                      new_policy=new_policy.value,
                      review_before_submit=session.review_before_submit):
        pass
    return {"session_id": session_id, "policy": session.policy.value,
            "review_before_submit": session.review_before_submit}


async def _assert_review_ready(session: FormSession, temporal: TemporalClient) -> None:
    if not session.review_before_submit or session.review_confirmed:
        raise HTTPException(409, "There is no form awaiting final review")
    state = await _current_state(session, temporal)
    await _refresh_review_readiness(session, temporal, state)
    if state.get("status") == "COMPLETED":
        # Closed workflows are necessarily past the final EndState; keep the
        # compatibility path used by mocks and older workers.
        if session.review_terminal_outcome != "exit_page":
            session.review_ready = True
    if not session.review_ready:
        raise HTTPException(409, "All questions must be answered before final review")
    if session.terminal_result is None:
        session.terminal_result = await _terminal_result(
            temporal, session.temporal_workflow_id, state
        )
    if (session.terminal_result or {}).get("outcome") == "exit_page":
        raise HTTPException(409, "An exit page is not a form for submission")


@app.post("/api/sessions/{session_id}/review/confirm")
@session_endpoint("forms.review.confirm")
async def confirm_review(session_id: str) -> dict[str, Any]:
    """Explicit final approval after Temporal has collected the form answers.

    The POC has no departmental submission integration. Approval marks the
    answer set as final; it does not repeat any Temporal input or send data.
    """
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    async with session.submission_lock:
        if session.review_confirmed:
            return {"review_confirmed": True}  # safe duplicate click
        temporal = await get_temporal_client()
        await _assert_review_ready(session, temporal)
        session.review_confirmed = True
        with session_span("forms.review.finalised", session,
                          answers=[_answer_data(item) for item in session.answer_history]):
            pass
    return {"review_confirmed": True}


async def _discard_replay(temporal: TemporalClient, workflow_id: str) -> None:
    """Best-effort cleanup of a failed replacement; original remains intact."""
    try:
        await temporal.get_workflow_handle(workflow_id).cancel()
    except Exception:
        logger.warning("Could not cancel abandoned review workflow %s", workflow_id)


@app.post("/api/sessions/{session_id}/review/amend")
@session_endpoint("forms.review.amend")
async def amend_review(session_id: str, req: ReviewAmendRequest) -> dict[str, Any]:
    """Revalidate a review edit through a new Temporal interpreter execution.

    No previously accepted value is silently edited in place. Replay follows
    the *new* authoritative SFSM path. If a changed answer alters routing or
    invalidates a later answer, hand that new question back to the user.
    """
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    async with session.submission_lock:
        temporal = await get_temporal_client()
        await _assert_review_ready(session, temporal)
        if req.revision != session.review_revision:
            raise HTTPException(409, "The answers have changed; refresh before editing")
        original = list(session.answer_history)
        if req.index < 0 or req.index >= len(original) or original[req.index].state_id != req.state_id:
            raise HTTPException(409, "This answer is no longer available for editing")
        if original[req.index].schema.get("kind") == "file_ref":
            raise HTTPException(422, "File uploads cannot be changed during final review")
        if original[req.index].value == req.value and type(original[req.index].value) is type(req.value):
            return await get_session_state(session_id)

        # Reuse the ORIGINAL definition, not a potentially updated export.
        new_id = f"sfsm-review-{uuid.uuid4().hex[:16]}"
        try:
            handle = await temporal.start_workflow(
                "SFSMInterpreter", arg=session.definition, id=new_id,
                task_queue=_task_queue(),
            )
            new_id = handle.id
        except Exception as exc:
            logger.exception("Unable to start replacement Temporal workflow")
            raise HTTPException(503, "Could not start review validation") from exc

        with session_span("forms.review.replay_start", session, original_workflow_id=session.temporal_workflow_id,
                          replacement_workflow_id=new_id, edited_index=req.index,
                          old_value=original[req.index].value, new_value=req.value,
                          old_answers=[_answer_data(item) for item in original]):
            pass
        rebuilt: list[AcceptedAnswer] = []
        try:
            state = await tool_functions.get_workflow_state(
                workflow_id=new_id, temporal_client=temporal
            )
            # A just-started Temporal workflow may not yet be awaiting input.
            if state.get("status") == "RUNNING" and not state.get("awaiting"):
                state = await _wait_for_workflow_progress(
                    temporal=temporal, workflow_id=new_id, previous_token=None,
                    initial_state=state, timeout_seconds=10.0,
                )
            for index, previous in enumerate(original):
                if state.get("status") == "COMPLETED":
                    break  # A new branch can terminate before later old answers.
                awaiting = state.get("awaiting")
                if not awaiting or state.get("status") == "ADVANCING":
                    raise HTTPException(503, "Replacement journey has not reached the next question")
                if awaiting.get("state_id") != previous.state_id:
                    if index <= req.index:
                        raise HTTPException(409, "The replacement journey changed before the edited question")
                    break  # Different branch: ask user to answer the NEW question.
                value = req.value if index == req.index else previous.value
                # Only a recognised real or mock ref from the same session can
                # be replayed; a mock is never represented as an uploaded file.
                if (awaiting.get("schema") or {}).get("kind") == "file_ref" and value is not None:
                    if not isinstance(value, dict):
                        raise HTTPException(409, "A previous file reference is no longer available")
                    references = session.mock_files if value.get("mock") is True else session.uploaded_files
                    if value.get("ref") not in references:
                        raise HTTPException(409, "A previous file reference is no longer available")
                try:
                    with session_span("forms.review.replay_input", session,
                                      replacement_workflow_id=new_id, original_index=index,
                                      state_id=awaiting.get("state_id"), token=awaiting["token"],
                                      schema=awaiting.get("schema"), submitted_value=value) as replay_span:
                        initial = await tool_functions.submit_input(
                            workflow_id=new_id, token=awaiting["token"], value=value,
                            temporal_client=temporal,
                        )
                        fields(replay_span, temporal_response=initial)
                except Exception as exc:
                    if index <= req.index:
                        # Invalid edited answer: original completed run is unaffected.
                        raise HTTPException(422, "The edited answer was rejected by the form") from exc
                    # An old downstream answer is invalid under the changed path:
                    # expose this *new* awaiting token to the user instead.
                    break
                rebuilt.append(AcceptedAnswer(
                    token=awaiting["token"],
                    state_id=awaiting.get("state_id") or "",
                    question_text=awaiting.get("prompt", ""),
                    schema=awaiting.get("schema") or {},
                    presentation=_lookup_state_presentation(
                        session.definition, awaiting.get("state_id")
                    ) or (awaiting.get("schema") or {}).get("presentation"),
                    value=value,
                    source="manual" if index == req.index else previous.source,
                    explanation="" if index == req.index else previous.explanation,
                ))
                state = await _wait_for_workflow_progress(
                    temporal=temporal, workflow_id=new_id,
                    previous_token=awaiting["token"], initial_state=initial,
                    timeout_seconds=10.0,
                )
            if state.get("status") == "ADVANCING" or (state.get("status") == "RUNNING" and not state.get("awaiting")):
                raise HTTPException(503, "Replacement journey has not finished advancing")
            if len(rebuilt) <= req.index:
                raise HTTPException(409, "Edited question is no longer on the new journey")
        except HTTPException:
            await _discard_replay(temporal, new_id)
            raise
        except Exception as exc:
            await _discard_replay(temporal, new_id)
            logger.exception("Review validation replay failed")
            raise HTTPException(503, "Could not validate the amended answers") from exc

        # Only NOW swap to the new authoritative Temporal run and its exact
        # accepted-answer path. The original completed run remains untouched.
        old_workflow_id = session.temporal_workflow_id
        session.temporal_workflow_id = new_id
        session.terminal_state = None  # A review edit has started a NEW execution.
        session.terminal_result = None
        session.review_ready = (state.get("status") == "COMPLETED"
                                or _is_mock_payment_input(state.get("awaiting")))
        session.review_terminal_outcome = None
        _remember_completion(session, state)
        session.accepted_tokens = {item.token for item in rebuilt}
        session.answer_history = rebuilt
        session.auto_answered = [AutoAnsweredQuestion(
            state_id=item.state_id, question_text=item.question_text,
            submitted_value=item.value, explanation=item.explanation,
        ) for item in rebuilt if item.source == "auto"]
        session.pending_submission_token = None
        session.pending_proposal = None
        session.review_revision += 1
        session.review_replay_needs_input = (state.get("status") != "COMPLETED"
                                             and not _is_mock_payment_input(state.get("awaiting")))
        with session_span("forms.review.replay_result", session, previous_workflow_id=old_workflow_id,
                          replacement_workflow_id=new_id, new_state=state,
                          rebuilt_answers=[_answer_data(item) for item in rebuilt]):
            pass
        # A chat agent created before the amendment may hold the old run ID.
        _agents.pop(session.session_id, None)
        # Do NOT call get_session_state while holding submission_lock: it only
        # queries Temporal, but a future version may need the same lock.
    return await get_session_state(session_id)


class UIEventRequest(BaseModel):
    action: str
    details: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/sessions/{session_id}/events")
@session_endpoint("forms.ui.event")
async def ui_event(session_id: str, req: UIEventRequest) -> dict[str, str]:
    """Small allowlisted UI event bridge for review actions invisible to the API."""
    allowed = {"review.enter", "review.edit_start", "review.edit_cancel", "review.return"}
    if req.action not in allowed:
        raise HTTPException(422, "Unsupported UI event")
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    with session_span("forms.review.ui", session, action=req.action, details=req.details,
                      answers=[_answer_data(item) for item in session.answer_history]):
        pass
    return {"status": "recorded"}


# --- Serve the built frontend ---

_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    port = int(_env("FORMS_FRONTEND_PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
