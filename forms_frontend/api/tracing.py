"""Evaluation-focused API tracing. Form/conversation payloads are intentionally retained.

Only infrastructure secrets (headers, credentials, environment) are excluded. This
is for synthetic prototype journeys, NOT a production telemetry/privacy policy.
"""
from __future__ import annotations

import functools
import itertools
import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode

from src.telemetry import FileSpanExporter, SessionSpanProcessor, session_id_var, workflow_id_var

if TYPE_CHECKING:
    from forms_frontend.api.sessions import FormSession

logger = logging.getLogger(__name__)
_provider: TracerProvider | None = None
_owned_provider = False


def configure_telemetry() -> None:
    """Idempotently attach an API JSONL exporter; never configure S3/SSM here.

    Existing SDK providers are reused instead of attempting to replace the
    OpenTelemetry process-global provider (which can only be set once).
    """
    global _provider, _owned_provider
    if _provider is not None:
        return
    path = Path(os.environ.get("FORMS_OTEL_EXPORT_FILE") or os.environ.get("OTEL_EXPORT_FILE")
                or Path(__file__).resolve().parents[2] / ".traces" / "forms-api-otel.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        provider = current
        _owned_provider = False
    else:
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        _owned_provider = True
    provider.add_span_processor(SessionSpanProcessor())
    provider.add_span_processor(BatchSpanProcessor(FileSpanExporter(path)))
    _provider = provider
    logger.info("Forms API OTEL JSONL: %s", path)


def shutdown_telemetry() -> None:
    global _provider, _owned_provider
    if _provider is not None:
        _provider.force_flush()
        if _owned_provider:
            _provider.shutdown()
        _provider = None
        _owned_provider = False


def as_json(value: Any) -> str:
    """OTEL cannot store dict/list attributes. Preserve nested payloads as JSON."""
    def default(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        return str(obj)
    return json.dumps(value, default=default, ensure_ascii=False)


def fields(span: Span, **items: Any) -> None:
    """All dynamic fields use a forms.* prefix; complex fields are JSON strings."""
    for key, value in items.items():
        try:
            span.set_attribute(key if key.startswith("forms.") else f"forms.{key}",
                               value if type(value) in (str, bool, int, float) else as_json(value))
        except Exception:
            # Evaluation instrumentation must never change form completion.
            logger.exception("Failed to annotate trace field %s", key)


def error(span: Span, exc: BaseException) -> None:
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, str(exc)))
    fields(span, error_type=type(exc).__name__, error_message=str(exc),
           http_status=getattr(exc, "status_code", None))


@contextmanager
def session_span(name: str, session: FormSession | None = None, **attrs: Any) -> Iterator[Span]:
    """Span + stable identifiers + monotonic per-session start sequence.

    The sequence orders span *starts*, not completions, including overlapping
    async requests. Separate HTTP requests are separate traces; IDs join them.
    """
    id_token = workflow_token = None
    if session is not None:
        id_token = session_id_var.set(session.session_id)
        workflow_token = workflow_id_var.set(session.temporal_workflow_id)
    try:
        with trace.get_tracer("forms_frontend.api").start_as_current_span(name) as span:
            if session is not None:
                # itertools.count.__next__ is atomic on this single-process POC's
                # CPython event loop, including synchronous interleavings.
                sequence = next(session.trace_sequence)
                fields(span, event_seq=sequence, session_id=session.session_id,
                       workflow_id=session.temporal_workflow_id,
                       form_id=session.form_id, policy=session.policy.value,
                       review_revision=session.review_revision)
                span.set_attribute("session_id", session.session_id)
                span.set_attribute("temporalWorkflowID", session.temporal_workflow_id)
            fields(span, **attrs)
            try:
                yield span
            except Exception as exc:
                error(span, exc)
                raise
    finally:
        if workflow_token is not None:
            workflow_id_var.reset(workflow_token)
        if id_token is not None:
            session_id_var.reset(id_token)


def session_endpoint(name: str) -> Callable:
    """FastAPI-safe decorator: functools.wraps preserves the endpoint signature."""
    def decorate(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def traced(*args: Any, **kwargs: Any) -> Any:
            # Import only at call time to avoid a main.py import cycle.
            from forms_frontend.api.main import store
            session = store.get(kwargs["session_id"])
            if session is None:
                return await fn(*args, **kwargs)  # original 404 handling
            request_data = {k: (v.model_dump() if hasattr(v, "model_dump") else v)
                            for k, v in kwargs.items()
                            if k not in ("session_id", "request")}
            with session_span(name, session, request=request_data,
                              pending_proposal=session.pending_proposal,
                              conversation=session.conversation_history):
                result = await fn(*args, **kwargs)
                # Do not serialise streaming response objects. SSE generators
                # create their own live trace context when actually iterated.
                if isinstance(result, (dict, list)):
                    trace.get_current_span().set_attribute("forms.response", as_json(result))
                return result
        return traced
    return decorate
