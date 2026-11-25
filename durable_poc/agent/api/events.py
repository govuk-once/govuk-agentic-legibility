"""Poll a Temporal SFSM run and yield transcript/awaiting-state diffs as events.

`watch_run()` is the generalized form of the polling loop that used to be
inlined as `stream_background_events()` inside `agent/chat.py`'s WebSocket
handler. It has no knowledge of WebSockets or SSE — both
`routes/runs.py` (SSE, for `/web` and `/agentic`) and `routes/chat_ws.py`
(WS, for `/chat`) drive it and translate `RunEvent`s to their own wire
format.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator, Literal

from temporalio.client import Client as TemporalClient

from agent import tools as tool_functions

RunEventType = Literal[
    "message", "options", "timeout", "trace", "completed", "escalation"
]

_TERMINAL_STATUSES = ("COMPLETED", "FAILED", "TERMINATED")


def clean_text_pipes(text: str) -> str:
    """Strip leading/trailing standalone vertical pipe characters from text lines."""
    if not text:
        return ""
    lines = [re.sub(r"^\s*\|\s*|\s*\|\s*$", "", line) for line in text.splitlines()]
    return "\n".join(lines).strip()


def get_options_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Extract human-readable options and schema kind generically from current awaiting state."""
    if not state:
        return {"kind": None, "options": []}

    awaiting = state.get("awaiting")
    if not awaiting:
        return {"kind": None, "options": []}

    if hasattr(awaiting, "__dict__"):
        awaiting = awaiting.__dict__
    if not isinstance(awaiting, dict):
        return {"kind": None, "options": []}

    schema = awaiting.get("schema") or {}
    if hasattr(schema, "__dict__"):
        schema = schema.__dict__
    if not isinstance(schema, dict):
        schema = {}

    kind = schema.get("kind") or awaiting.get("state_type")
    if kind == "boolean":
        return {"kind": "boolean", "options": ["Yes", "No"]}

    raw_options = (
        awaiting.get("options")
        or schema.get("options")
        or (
            schema.get("schema", {}).get("options")
            if isinstance(schema.get("schema"), dict)
            else None
        )
        or []
    )

    if not isinstance(raw_options, list) or not raw_options:
        return {"kind": kind, "options": []}

    label_key = schema.get("label_key")
    value_key = schema.get("value_key")

    choices = []
    for opt in raw_options:
        if isinstance(opt, dict):
            label = None
            if label_key and opt.get(label_key) is not None:
                label = opt.get(label_key)

            if label is None:
                label = (
                    opt.get("label")
                    or opt.get("single_line")
                    or opt.get("name")
                    or opt.get("title")
                    or opt.get("description")
                    or (opt.get(value_key) if value_key else None)
                    or opt.get("id")
                    or opt.get("value")
                )

            if label is None:
                str_vals = [v for v in opt.values() if isinstance(v, str)]
                label = str_vals[0] if str_vals else str(opt)

            choices.append(str(label))
        elif hasattr(opt, "label"):
            choices.append(str(getattr(opt, "label")))
        elif hasattr(opt, "value"):
            choices.append(str(getattr(opt, "value")))
        else:
            choices.append(str(opt))

    return {"kind": kind, "options": choices}


@dataclass
class RunEvent:
    """One diff emitted while watching a run: a new transcript line, the
    options for a newly-awaiting field, its timeout, an engine trace entry,
    or the run reaching a terminal status."""

    type: RunEventType
    role: str | None = None
    text: str | None = None
    kind: str | None = None
    options: list[str] | None = None
    seconds: int | None = None
    category: str | None = None
    summary: str | None = None
    detail: Any = None
    status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form, omitting fields this event type doesn't use."""
        return {k: v for k, v in asdict(self).items() if v is not None}


async def watch_run(
    workflow_id: str,
    temporal_client: TemporalClient,
    *,
    poll_interval: float = 0.5,
) -> AsyncIterator[RunEvent]:
    """Poll one Temporal SFSM run and yield state diffs until it terminates.

    Args:
        workflow_id: Temporal execution ID to poll.
        temporal_client: Untraced polling client (see `deps.get_polling_client`).
        poll_interval: Seconds between `get_workflow_state` queries.

    Yields:
        `RunEvent`s for each new transcript line, newly-awaiting field
        (options + timeout), engine trace line, and finally one `completed`
        event once the run reaches a terminal status.
    """
    last_seen_index = 0
    handled_tokens: set[str] = set()

    while True:
        try:
            state = await tool_functions.get_workflow_state(
                workflow_id=workflow_id, temporal_client=temporal_client
            )
        except Exception:
            await asyncio.sleep(poll_interval)
            continue

        transcript = state.get("transcript") or []
        current_len = len(transcript)
        awaiting = state.get("awaiting")
        token = awaiting.get("token") if awaiting else None
        execution_status = state.get("status", "RUNNING")

        if current_len > last_seen_index:
            for idx in range(last_seen_index, current_len):
                entry = transcript[idx]
                msg_text = (
                    entry.get("message")
                    if isinstance(entry, dict)
                    else getattr(entry, "message", "")
                )
                clean_msg = clean_text_pipes(msg_text)

                if clean_msg.startswith("[ENGINE LOG]"):
                    yield RunEvent(
                        type="trace",
                        category="ENGINE",
                        summary="FSM Execution Event",
                        detail=clean_msg.replace("[ENGINE LOG]", "").strip(),
                    )
                else:
                    yield RunEvent(type="message", role="assistant", text=clean_msg)
                    yield RunEvent(
                        type="trace",
                        category="ENGINE",
                        summary="OutputState Transcript Emitted",
                        detail=clean_msg,
                    )
            last_seen_index = current_len

        if token and token not in handled_tokens:
            handled_tokens.add(token)
            clean_prompt = clean_text_pipes(awaiting.get("prompt", "")) if awaiting else ""
            if clean_prompt:
                yield RunEvent(type="message", role="assistant", text=clean_prompt)
                yield RunEvent(
                    type="trace",
                    category="ENGINE",
                    summary=f"Awaiting InputState [{token}]",
                    detail={"prompt": clean_prompt, "schema": awaiting.get("schema")},
                )

            opts = get_options_from_state(state)
            yield RunEvent(type="options", kind=opts["kind"], options=opts["options"])

            timeout_seconds = awaiting.get("timeout_seconds") if awaiting else None
            if timeout_seconds is not None:
                yield RunEvent(type="timeout", seconds=timeout_seconds)

        if not awaiting and execution_status in _TERMINAL_STATUSES:
            yield RunEvent(type="completed", status=execution_status)
            return

        await asyncio.sleep(poll_interval)
