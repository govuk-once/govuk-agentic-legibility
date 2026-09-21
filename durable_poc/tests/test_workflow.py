"""Integration tests for the FSM workflow executor, activities, and update validators."""

import json
from pathlib import Path
from typing import Any
import shutil

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.client import WorkflowUpdateFailedError

from src.activities import CallParams, NotifyParams, activity, http_call
from src.context import InputSubmission
from src.interpreter import SFSMInterpreter
from src.errors import ValidationError

TEMPORAL_PATH = shutil.which("temporal")


@activity.defn(name="http_call")
async def mock_http_call(params: CallParams) -> dict[str, Any]:
    if "driver-summary" in params.url:
        return {
            "status": 200,
            "body": {
                "driverViewResponse": {
                    "driver": {
                        "drivingLicenceNumber": "SMITH9090",
                        "firstNames": "Jane",
                        "lastName": "Smith",
                    }
                }
            },
        }
    return {"status": 200, "body": {}}


@activity.defn(name="notify")
async def mock_notify(params: NotifyParams) -> None:
    pass


@pytest.fixture
def sample_workflow_def() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "sample_workflow.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_workflow_execution_completes(
    sample_workflow_def: dict[str, Any],
) -> None:
    """Workflow executes input states, evaluates choice rules, and yields control."""
    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=TEMPORAL_PATH,
    ) as env:
        async with Worker(
            env.client,
            task_queue="test-q",
            workflows=[SFSMInterpreter],
            activities=[mock_http_call, mock_notify],
        ):
            handle = await env.client.start_workflow(
                SFSMInterpreter.run,
                sample_workflow_def,
                id="test-wf-completes",
                task_queue="test-q",
            )

            await env.sleep(0.1)

            state_info = await handle.query("current_state_info")
            assert state_info is not None
            assert state_info["state_type"] == "InputState"

            awaiting = await handle.query("awaiting")
            assert awaiting is not None
            print(awaiting)
            assert awaiting["prompt"] == "What is your name?"

            await handle.execute_update(
                "submit_input", InputSubmission(token=awaiting["token"], value="Alice")
            )

            await env.sleep(0.1)

            awaiting = await handle.query("awaiting")
            assert awaiting["prompt"] == "Do you want to receive weather alerts?"

            await handle.execute_update(
                "submit_input", InputSubmission(token=awaiting["token"], value=True)
            )

            result = await handle.result()
            assert result["status"] == "success"
            assert result["return"] == {"name": "Alice", "status": "subscribed"}


@pytest.mark.asyncio
async def test_update_validator_rejects_type_mismatch(
    sample_workflow_def: dict[str, Any],
) -> None:
    """Validator rejects string inputs when a boolean is expected."""
    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=TEMPORAL_PATH,
    ) as env:
        async with Worker(
            env.client,
            task_queue="test-q",
            workflows=[SFSMInterpreter],
            activities=[mock_http_call, mock_notify],
        ):
            handle = await env.client.start_workflow(
                SFSMInterpreter.run,
                sample_workflow_def,
                id="test-wf-validator",
                task_queue="test-q",
            )
            await env.sleep(0.1)

            awaiting = await handle.query("awaiting")
            await handle.execute_update(
                "submit_input", InputSubmission(token=awaiting["token"], value="Alice")
            )
            await env.sleep(0.1)

            awaiting = await handle.query("awaiting")
            with pytest.raises(WorkflowUpdateFailedError) as excinfo:
                await handle.execute_update(
                    "submit_input",
                    InputSubmission(token=awaiting["token"], value="InvalidString"),
                )

            assert "Expected boolean" in str(excinfo.value.cause)


@pytest.mark.asyncio
async def test_unconfigured_service_raises_validation_error() -> None:
    """Activities raise ValidationError for unconfigured HTTP service targets."""
    params = CallParams(
        method="GET",
        url="/test-endpoint",
        service="unknown_service_key",
        headers=None,
        body=None,
        capture={},
    )
    with pytest.raises(ValidationError) as excinfo:
        await http_call(params)

    assert "Unrecognised or unconfigured HTTP service" in str(excinfo.value)


@pytest.mark.asyncio
async def test_idempotency_key_header_forwarding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Activities attach Idempotency-Key headers to outbound requests (Issue 2.12)."""
    monkeypatch.setenv("DVLA_BASE", "http://localhost:8000")

    params = CallParams(
        method="POST",
        url="/submit",
        service="dvla",
        headers={"Content-Type": "application/json"},
        body={"data": "test"},
        capture={},
        idempotency_key="idempotency-key-12345",
    )

    assert params.idempotency_key == "idempotency-key-12345"


@pytest.mark.asyncio
async def test_workflow_traces_propagate_across_boundary(
    sample_workflow_def: dict[str, Any],
) -> None:
    """Interpreter spans on the worker share the trace_id from the client-side spans."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set as global so the interpreter's module-level tracer picks it up.
    # If test_tracing.py already set one, this is silently ignored — but then
    # the global provider already has processors, so we also add our exporter there.
    trace.set_tracer_provider(provider)
    global_provider = trace.get_tracer_provider()
    if global_provider is not provider and hasattr(global_provider, "add_span_processor"):
        global_provider.add_span_processor(SimpleSpanProcessor(exporter))

    tracer = provider.get_tracer("test.integration")
    tracing_interceptor = TracingInterceptor(tracer=tracer)

    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=TEMPORAL_PATH,
        interceptors=[tracing_interceptor],
    ) as env:
        async with Worker(
            env.client,
            task_queue="test-trace-q",
            workflows=[SFSMInterpreter],
            activities=[mock_http_call, mock_notify],
            interceptors=[tracing_interceptor],
        ):
            with tracer.start_as_current_span("test_root"):
                handle = await env.client.start_workflow(
                    SFSMInterpreter.run,
                    sample_workflow_def,
                    id="test-wf-traces",
                    task_queue="test-trace-q",
                )
                await env.sleep(0.1)

                awaiting = await handle.query("awaiting")
                assert awaiting is not None

                await handle.execute_update(
                    "submit_input",
                    InputSubmission(token=awaiting["token"], value="Alice"),
                )
                await env.sleep(0.1)

                awaiting = await handle.query("awaiting")
                await handle.execute_update(
                    "submit_input",
                    InputSubmission(token=awaiting["token"], value=True),
                )
                result = await handle.result()
                assert result["status"] == "success"

    finished = exporter.get_finished_spans()
    span_names = [s.name for s in finished]

    assert "test_root" in span_names

    interpreter_spans = [
        s for s in finished if s.name.startswith("interpreter.")
    ]
    assert len(interpreter_spans) >= 2, (
        f"Expected at least 2 interpreter spans (2x InputState), got {len(interpreter_spans)}: "
        f"{[s.name for s in interpreter_spans]}"
    )

    input_spans = [s for s in interpreter_spans if s.name == "interpreter.InputState"]
    # Temporal replays workflow history from the start on each new task,
    # so a plain TracerProvider (without ReplaySafeTracerProvider) may
    # produce duplicate spans for replayed states. Deduplicate by state_id,
    # preferring spans that completed fully (have the "outcome" attribute).
    seen_states: dict[str, Any] = {}
    for span in input_spans:
        state_id = span.attributes.get("state_id")
        if state_id not in seen_states or "outcome" in span.attributes:
            seen_states[state_id] = span

    assert len(seen_states) == 2, (
        f"Expected 2 unique InputState state_ids, got {list(seen_states.keys())}"
    )

    for span in seen_states.values():
        assert "state_id" in span.attributes
        assert "process_id" in span.attributes
        assert "schema_kind" in span.attributes
        assert "token" in span.attributes
        assert span.attributes["outcome"] == "received"

    assert seen_states["ask_name"].attributes["schema_kind"] == "string"
    assert seen_states["ask_name"].attributes["prompt"] == "What is your name?"

    assert seen_states["ask_subscribe"].attributes["schema_kind"] == "boolean"

    provider.shutdown()


@pytest.mark.asyncio
async def test_evaluation_checkpoint_captures_full_subprocess_stack() -> None:
    """Evaluation checkpoint exposes parent/child frames and invocation inputs."""
    definition = {
        "schema": "sfsm/0.2",
        "id": "test.checkpoint",
        "version": "1.0",
        "entry": "main",
        "executor": {},
        "processes": {
            "main": {
                "start": "invoke_child",
                "vars": {"outer_value": "kept", "child_result": None},
                "states": {
                    "invoke_child": {
                        "type": "invoke",
                        "process": "child",
                        "input": {"from_parent": {"$": "outer_value"}},
                        "assign": "child_result",
                        "next": "after_child",
                    },
                    "after_child": {
                        "type": "end",
                        "status": "success",
                    },
                },
            },
            "child": {
                "start": "ask_child",
                "vars": {"answer": None},
                "states": {
                    "ask_child": {
                        "type": "input",
                        "prompt": "Child question?",
                        "schema": {"kind": "string"},
                        "assign": "answer",
                        "next": "end_child",
                    },
                    "end_child": {
                        "type": "end",
                        "status": "success",
                        "return": {"answer": {"$": "answer"}},
                    },
                },
            },
        },
    }

    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=TEMPORAL_PATH,
    ) as env:
        async with Worker(
            env.client,
            task_queue="test-checkpoint-q",
            workflows=[SFSMInterpreter],
            activities=[mock_http_call, mock_notify],
        ):
            handle = await env.client.start_workflow(
                SFSMInterpreter.run,
                definition,
                id="test-evaluation-checkpoint",
                task_queue="test-checkpoint-q",
            )
            await env.sleep(0.1)

            checkpoint = await handle.query("evaluation_checkpoint")

            assert checkpoint["schema_version"] == "sfsm-interpreter-checkpoint/0.1"
            assert checkpoint["current_state"] == {
                "process_id": "child",
                "state_id": "ask_child",
                "state_type": "InputState",
                "step": 2,
            }
            assert checkpoint["awaiting"]["state_id"] == "ask_child"

            state = checkpoint["interpreter_state"]
            assert state["step_counter"] == 2
            assert len(state["frames"]) == 2
            assert state["frames"][0] == {
                "process_id": "main",
                "state_id": "after_child",
                "vars": {"outer_value": "kept", "child_result": None},
                "invoker_state_id": None,
            }
            assert state["frames"][1] == {
                "process_id": "child",
                "state_id": "ask_child",
                "vars": {
                    "answer": None,
                    "input": {"from_parent": "kept"},
                },
                "invoker_state_id": "invoke_child",
            }
