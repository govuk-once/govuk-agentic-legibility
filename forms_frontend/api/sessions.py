"""In-memory session management for form completions.

Each session binds a browser session to a Temporal workflow execution,
an agent conversation, and an interaction policy.

Temporal remains the source of truth for workflow progression.
Sessions track only the association and transient UI state.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InteractionPolicy(str, Enum):
    MANUAL = "manual"
    CONFIRM = "confirm"
    AUTO = "auto"


@dataclass
class AutoAnsweredQuestion:
    """Record of a question the agent answered automatically."""

    state_id: str
    question_text: str
    submitted_value: Any
    explanation: str = ""


@dataclass
class AcceptedAnswer:
    """An accepted Temporal input, in the order actually traversed.

    This is review/display history, not a second journey executor. The SFSM
    interpreter remains the authority for validation and routing.
    """

    token: str
    state_id: str
    question_text: str
    schema: dict[str, Any]
    presentation: dict[str, Any] | None
    value: Any
    source: str  # manual, confirm or auto
    explanation: str = ""


@dataclass
class FormSession:
    session_id: str
    form_id: str
    temporal_workflow_id: str
    form_metadata: dict[str, Any]
    definition: dict[str, Any]
    policy: InteractionPolicy = InteractionPolicy.MANUAL
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    auto_answered: list[AutoAnsweredQuestion] = field(default_factory=list)
    answer_history: list[AcceptedAnswer] = field(default_factory=list)
    review_before_submit: bool = False
    review_confirmed: bool = False
    review_revision: int = 0
    review_replay_needs_input: bool = False
    # A completed Temporal execution cannot revert to an awaiting question.
    # Cache the authoritative terminal observation for this execution only.
    terminal_state: dict[str, Any] | None = None
    terminal_result: dict[str, Any] | None = None
    pending_proposal: dict[str, Any] | None = None
    # Transient HTTP/SSE coordination only. Temporal remains authoritative.
    submission_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    accepted_tokens: set[str] = field(default_factory=set)
    pending_submission_token: str | None = None
    # Opaque local refs permitted for this session and current input token.
    uploaded_files: dict[str, tuple[str, int, str]] = field(default_factory=dict)


class SessionStore:
    """Thread-safe in-memory session store.

    Limitations (acceptable for POC):
    - Sessions lost on server restart.
    - No cross-process sharing.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, FormSession] = {}

    def create(
        self,
        *,
        form_id: str,
        temporal_workflow_id: str,
        form_metadata: dict[str, Any],
        definition: dict[str, Any],
        policy: InteractionPolicy = InteractionPolicy.MANUAL,
        review_before_submit: bool = False,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> FormSession:
        session_id = str(uuid.uuid4())
        session = FormSession(
            session_id=session_id,
            form_id=form_id,
            temporal_workflow_id=temporal_workflow_id,
            form_metadata=form_metadata,
            definition=definition,
            policy=policy,
            review_before_submit=review_before_submit,
            conversation_history=conversation_history or [],
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> FormSession | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_all(self) -> list[FormSession]:
        return list(self._sessions.values())
