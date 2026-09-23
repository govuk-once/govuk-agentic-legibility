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
import sys
import tempfile
import ipaddress
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from temporalio.client import Client as TemporalClient
from temporalio.contrib.opentelemetry import TracingInterceptor

# durable_poc imports — available via PYTHONPATH=durable_poc
from agent import tools as tool_functions
from agent.agent import WorkflowAgent

from forms_frontend.api.sessions import (
    AutoAnsweredQuestion,
    FormSession,
    InteractionPolicy,
    SessionStore,
)
from forms_frontend.api.proposals import propose_answer
from forms_frontend.api.uploads import InvalidUpload, save_local_upload

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

app = FastAPI(title="GOV.UK Forms Frontend API")

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


async def _current_state(session: FormSession, temporal: TemporalClient) -> dict[str, Any]:
    """Mask a consumed input while the next authoritative state is not ready."""
    state = await tool_functions.get_workflow_state(
        workflow_id=session.temporal_workflow_id, temporal_client=temporal
    )
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


async def _submit_once(
    session: FormSession, temporal: TemporalClient, token: str, value: Any,
    *, auto_record: AutoAnsweredQuestion | None = None,
) -> tuple[dict[str, Any], bool]:
    """Token-guarded submission shared by manual, Confirm and Auto policies.

    An accepted update is never sent twice, even if a subsequent Temporal query
    still returns the previous input. The lock also serialises SSE and HTTP
    submissions for this (single-process POC) session.
    """
    async with session.submission_lock:
        state = await _current_state(session, temporal)
        if token in session.accepted_tokens:
            return state, False
        awaiting = state.get("awaiting") or {}
        if awaiting.get("token") != token:
            raise HTTPException(409, "This question is no longer awaiting an answer")
        if (awaiting.get("schema") or {}).get("kind") == "file_ref":
            _check_file_submission(session, token, value)

        # The Temporal update validator rejects invalid values and stale tokens;
        # record acceptance *only after* the update returns successfully.
        initial = await tool_functions.submit_input(
            workflow_id=session.temporal_workflow_id,
            token=token, value=value, temporal_client=temporal,
        )
        session.accepted_tokens.add(token)
        # Record accepted automatic answers immediately, not after polling.
        # A browser closing the SSE stream during the next-state wait must
        # not silently lose a submission from the cumulative summary.
        if auto_record is not None:
            session.auto_answered.append(auto_record)
        session.pending_submission_token = token
        state = await _wait_for_workflow_progress(
            temporal=temporal,
            workflow_id=session.temporal_workflow_id,
            previous_token=token, initial_state=initial,
        )
        if state["status"] != "ADVANCING":
            session.pending_submission_token = None
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


# =====================================================================
# Request/Response models
# =====================================================================


class StartSessionRequest(BaseModel):
    form_id: str | int
    policy: str = "manual"
    fixture_id: str | None = None


class StartSessionResponse(BaseModel):
    session_id: str
    form_id: str
    form_name: str
    temporal_workflow_id: str
    policy: str
    fixture_id: str | None = None
    conversation_messages: int = 0


class SubmitAnswerRequest(BaseModel):
    token: str
    value: Any


class ChatRequest(BaseModel):
    message: str


class PolicyRequest(BaseModel):
    policy: str


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
    http = await get_http_client()
    temporal = await get_temporal_client()

    definition = await tool_functions.get_workflow_definition(
        workflow_id=req.form_id, http_client=http, base_url=_workflow_server_url()
    )

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
        conversation_history=conversation_history,
    )

    return StartSessionResponse(
        session_id=session.session_id,
        form_id=session.form_id,
        form_name=form_metadata.get("name", f"Form {req.form_id}"),
        temporal_workflow_id=temporal_workflow_id,
        policy=session.policy.value,
        fixture_id=req.fixture_id,
        conversation_messages=len(conversation_history),
    )


@app.get("/api/sessions/{session_id}/state")
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

    return {
        "session_id": session_id,
        "workflow_id": session.temporal_workflow_id,
        "status": state.get("status", "RUNNING"),
        "awaiting": awaiting,
        "presentation": presentation,
        "form_metadata": session.form_metadata,
        "policy": session.policy.value,
        "answered_count": len(session.accepted_tokens),
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
        "result": await _terminal_result(temporal, session.temporal_workflow_id, state),
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
    recorded = session.uploaded_files.get(ref) if isinstance(ref, str) else None
    if recorded != (token, value.get("bytes"), value.get("content_type")):
        raise HTTPException(422, "File reference was not uploaded for this question")


@app.post("/api/sessions/{session_id}/files")
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
async def chat(session_id: str, req: ChatRequest) -> dict[str, Any]:
    """Send a conversational message to the agent."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    agent = _get_or_create_agent(session)
    temporal = await get_temporal_client()

    state = await tool_functions.get_workflow_state(
        workflow_id=session.temporal_workflow_id, temporal_client=temporal
    )

    session.conversation_history.append({"role": "user", "content": req.message})

    try:
        response = await agent.respond(req.message, context=state)
    except Exception as e:
        logger.exception("Agent respond failed for session %s", session_id)
        raise HTTPException(status_code=502, detail=f"Agent error: {e}")

    session.conversation_history.append({"role": "assistant", "content": response})

    updated_state = await tool_functions.get_workflow_state(
        workflow_id=session.temporal_workflow_id, temporal_client=temporal
    )

    return {
        "response": response,
        "state": updated_state,
    }


@app.post("/api/sessions/{session_id}/propose")
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

    proposal = await propose_answer(
        conversation_history=session.conversation_history,
        awaiting=awaiting,
    )
    logger.info("Proposal result for session %s: %s", session_id, proposal)

    if not proposal.get("has_answer"):
        session.pending_proposal = None
        return proposal

    if session.policy == InteractionPolicy.CONFIRM:
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
        if not awaiting:
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
        except Exception:
            logger.exception("Auto-progress submission failed")
            break

        if submitted:
            steps_taken += 1

        if state.get("status") == "ADVANCING":
            break

        awaiting = state.get("awaiting")
        if not awaiting:
            break

        proposal = await propose_answer(
            conversation_history=session.conversation_history,
            awaiting=awaiting,
        )

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
async def auto_progress_stream(session_id: str, request: Request) -> EventSourceResponse:
    """Stream auto-progress events as the agent steps through questions.

    Each SSE event is a JSON object with type: "step", "waiting", or "done".
    """
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.policy != InteractionPolicy.AUTO:
        raise HTTPException(status_code=409, detail="Automatic mode is not enabled")

    async def event_generator():
        temporal = await get_temporal_client()
        state = await _current_state(session, temporal)

        # Count total input states in the definition for progress denominator
        total_questions = 0
        for proc in session.definition.get("processes", {}).values():
            for s in proc.get("states", {}).values():
                if s.get("type") == "input":
                    total_questions += 1

        steps_taken = len(session.auto_answered)
        steps_this_run = 0
        max_steps = 20

        while steps_this_run < max_steps:
            if await request.is_disconnected():
                break
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
                awaiting=awaiting,
            )

            if not proposal.get("has_answer"):
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
            except Exception:
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

    return EventSourceResponse(event_generator())


@app.post("/api/sessions/{session_id}/confirm-proposal")
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
        new_state, submitted = await _submit_once(session, temporal, token, value)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Confirmed proposals require user authorisation and are not *automatic*
    # answers. They do contribute to accepted journey progress, via the token.
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
async def reject_proposal(session_id: str) -> dict[str, Any]:
    """Reject the pending proposal — user will answer manually."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.pending_proposal = None
    return {"status": "rejected"}


@app.put("/api/sessions/{session_id}/policy")
async def set_policy(session_id: str, req: PolicyRequest) -> dict[str, Any]:
    """Change the interaction policy for a session."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        session.policy = InteractionPolicy(req.policy)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy. Must be one of: {[p.value for p in InteractionPolicy]}",
        )

    return {"session_id": session_id, "policy": session.policy.value}


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
