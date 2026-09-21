"""Run one targeted durable-workflow interaction repeatedly against the real agent."""

from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from typing import Any
from uuid import uuid4

import yaml
from temporalio.client import Client

from agent.agent import WorkflowAgent
from src.context import InterpreterState, StackFrame, TranscriptEntry
from src.interpreter import SFSMInterpreter
from evaluation.otel_common_trace import convert_trace
from evaluation.scenario_case import checkpoint_target, load_document, load_scenario_case

DURABLE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DURABLE_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    # The durable runner is normally invoked from durable_poc/, while the shared
    # implementation-independent evaluator lives in the sibling agents package.
    sys.path.insert(0, str(REPO_ROOT))

from agents.src.scenario_evaluation.evaluator import (  # noqa: E402
    EvaluationResult,
    evaluate_common_trace,
)

DEFAULT_DEFINITION = DURABLE_ROOT / "dwp_ma1_schema.json"
DEFAULT_OTEL_TRACE = Path(".traces") / "durable-otel.jsonl"
DEFAULT_OUTPUT_DIR = Path(".traces") / "evaluation-runs"
DEFAULT_BATCH_OUTPUT_DIR = Path(".traces") / "evaluation-batches"
DEFAULT_TRACE_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class TargetedRunResult:
    """Artifacts and semantic result for one targeted durable evaluation run."""

    attempt: int
    scenario_id: str
    workflow_id: str
    common_trace_path: Path | None
    evaluation: EvaluationResult | None
    execution_error: str | None
    duration_ms: float

    @property
    def outcome(self) -> str:
        if self.execution_error is not None or self.evaluation is None:
            return "error"
        return "pass" if self.evaluation.passed else "fail"



def build_checkpoint_state(
    definition: dict[str, Any],
    checkpoint: dict[str, Any],
) -> InterpreterState:
    """Rehydrate a captured semantic InterpreterState for a fresh workflow run."""
    if checkpoint.get("schema_version") != "sfsm-interpreter-checkpoint/0.1":
        raise ValueError(
            "Unsupported checkpoint schema version: "
            f"{checkpoint.get('schema_version')!r}"
        )

    # Validate the semantic target before rebuilding the stack. The checkpoint is
    # authoritative for the target interaction; scenario.yaml does not duplicate it.
    checkpoint_target(checkpoint)

    captured = checkpoint.get("interpreter_state")
    if not isinstance(captured, dict):
        raise ValueError("Captured checkpoint is missing interpreter_state")

    raw_frames = captured.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        raise ValueError("Captured checkpoint must contain at least one frame")

    frames: list[StackFrame] = []
    for raw_frame in raw_frames:
        if not isinstance(raw_frame, dict):
            raise ValueError("Captured checkpoint frames must be objects")
        process_id = raw_frame.get("process_id")
        state_id = raw_frame.get("state_id")
        variables = raw_frame.get("vars")
        if (
            not isinstance(process_id, str)
            or not isinstance(state_id, str)
            or not isinstance(variables, dict)
        ):
            raise ValueError("Captured checkpoint contains an invalid frame")

        process = definition.get("processes", {}).get(process_id)
        if not isinstance(process, dict) or state_id not in process.get("states", {}):
            raise ValueError(
                f"Captured checkpoint references missing state {process_id}.{state_id}"
            )

        invoker_state_id = raw_frame.get("invoker_state_id")
        if invoker_state_id is not None and not isinstance(invoker_state_id, str):
            raise ValueError("invoker_state_id must be a string or null")

        frames.append(
            StackFrame(
                process_id=process_id,
                state_id=state_id,
                vars=deepcopy(variables),
                # Keep this serialisable across the Temporal start boundary. The
                # interpreter rehydrates the real InvokeState from the definition.
                invoker_state=invoker_state_id,
            )
        )

    transcript: list[TranscriptEntry] = []
    for raw_entry in captured.get("transcript", []):
        if not isinstance(raw_entry, dict):
            raise ValueError("Captured transcript entries must be objects")
        transcript.append(
            TranscriptEntry(
                step=int(raw_entry["step"]),
                timestamp=str(raw_entry["timestamp"]),
                message=str(raw_entry["message"]),
            )
        )

    step_counter = captured.get("step_counter")
    if not isinstance(step_counter, int) or step_counter < 1:
        raise ValueError("Captured checkpoint step_counter must be a positive integer")

    env = captured.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("Captured checkpoint env must be an object")

    # The snapshot is taken while the current InputState is already suspended at
    # step N. A fresh workflow starts just before executing that state, so use
    # N-1 here; the interpreter's next loop iteration recreates the same step N
    # and a fresh awaiting-input token.
    return InterpreterState(
        frames=frames,
        transcript=transcript,
        step_counter=step_counter - 1,
        env=deepcopy(env),
    )

def agent_input(
    fixture: dict[str, Any], current_prompt: str
) -> tuple[list[dict[str, Any]], str]:
    """Return seeded Strands history and the final user turn under test."""
    conversation = fixture["conversation"]
    if not conversation or conversation[-1].get("role") != "user":
        raise ValueError("Fixture must end with the user turn under test")

    history = list(conversation[:-1])
    current_user_message = conversation[-1]["content"]

    # The authoritative current prompt is supplied again by build_contextual_prompt().
    if (
        history
        and history[-1].get("role") == "assistant"
        and history[-1].get("content") == current_prompt
    ):
        history.pop()

    messages = [
        {"role": item["role"], "content": [{"text": item["content"]}]}
        for item in history
    ]
    return messages, current_user_message


async def wait_for_input(agent: WorkflowAgent, workflow_id: str) -> dict[str, Any]:
    for _ in range(30):
        state = await agent.call_tool("get_workflow_state", workflow_id=workflow_id)
        if state.get("awaiting"):
            return state
        await asyncio.sleep(0.1)
    raise RuntimeError(f"Workflow {workflow_id} did not reach an input state")


async def wait_for_common_trace(
    *,
    trace_path: Path,
    scenario_path: Path,
    workflow_id: str,
    timeout_seconds: float,
    require_submission: bool = False,
) -> dict[str, Any]:
    """Wait for target executor evidence to reach OTEL JSONL."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    last_error: Exception | None = None

    while True:
        try:
            common_trace = convert_trace(
                trace_path=trace_path,
                scenario_path=scenario_path,
                workflow_id=workflow_id,
            )
            if require_submission and not any(
                event.get("type") == "values_submitted"
                for event in common_trace.get("events", [])
                if isinstance(event, dict)
            ):
                last_error = ValueError(
                    "Rejected submission observed; waiting for accepted InputState span"
                )
            else:
                return common_trace
        except FileNotFoundError as error:
            last_error = error
        except ValueError as error:
            message = str(error)
            if not (
                message.startswith(
                    "No accepted or rejected input span found"
                )
                or message.startswith("Invalid JSON on")
            ):
                raise
            last_error = error

        if loop.time() >= deadline:
            detail = f": {last_error}" if last_error is not None else ""
            raise RuntimeError(
                f"Timed out after {timeout_seconds:g}s waiting for OTEL trace "
                f"for {workflow_id}{detail}"
            )
        await asyncio.sleep(0.2)


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(value, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, separators=(",", ":")))
        handle.write("\n")


def evaluation_record(
    result: TargetedRunResult,
    *,
    batch_id: str,
    scenario_path: Path,
    model_id: str,
    otel_trace: Path,
    evaluation_path: Path,
) -> dict[str, Any]:
    issues = []
    if result.evaluation is not None:
        issues = [
            {"path": issue.path, "message": issue.message}
            for issue in result.evaluation.issues
        ]
    return {
        "schema_version": "0.1",
        "batch_id": batch_id,
        "scenario_id": result.scenario_id,
        "scenario_path": str(scenario_path),
        "attempt": result.attempt,
        "run_id": result.workflow_id,
        "model_id": model_id,
        "outcome": result.outcome,
        "passed": result.outcome == "pass",
        "issues": issues,
        "execution_error": result.execution_error,
        "duration_ms": result.duration_ms,
        "otel_trace": str(otel_trace),
        "common_trace": (
            str(result.common_trace_path)
            if result.common_trace_path is not None
            else None
        ),
        "evaluation": str(evaluation_path),
    }


def new_batch_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex[:8]}"


async def run_once(
    attempt: int,
    *,
    scenario: dict[str, Any],
    scenario_path: Path,
    definition: dict[str, Any],
    checkpoint: dict[str, Any],
    initial_messages: list[dict[str, Any]],
    current_user_message: str,
    temporal_client: Client,
    temporal_address: str,
    task_queue: str,
    workflow_server_url: str,
    model_id: str,
    region: str,
    otel_trace: Path,
    output_dir: Path,
    trace_timeout_seconds: float,
    semaphore: asyncio.Semaphore,
) -> TargetedRunResult:
    async with semaphore:
        started = perf_counter()
        scenario_id = scenario["id"]
        workflow_id = f"eval-{scenario_id}-{uuid4().hex[:8]}"
        handle = None
        agent = None
        common_trace_path: Path | None = None
        evaluation: EvaluationResult | None = None
        execution_error: str | None = None

        try:
            handle = await temporal_client.start_workflow(
                SFSMInterpreter.run,
                args=[
                    definition,
                    build_checkpoint_state(definition, checkpoint),
                ],
                id=workflow_id,
                task_queue=task_queue,
            )
            agent = WorkflowAgent(
                workflow_server_url=workflow_server_url,
                model_id=model_id,
                region_name=region,
                temporal_address=temporal_address,
                task_queue=task_queue,
                conversation_history=deepcopy(initial_messages),
            )

            before = await wait_for_input(agent, workflow_id)
            before_id = before["awaiting"]["state_id"]

            respond_error: Exception | None = None
            try:
                await agent.respond(current_user_message, context=before)
            except Exception as error:  # noqa: BLE001 - rejected inputs are eval evidence
                respond_error = error

            after = agent.session_state or {}
            awaiting = after.get("awaiting")
            after_id = awaiting.get("state_id") if isinstance(awaiting, dict) else None

            workflow_advanced = awaiting is None or after_id != before_id
            try:
                common_trace = await wait_for_common_trace(
                    trace_path=otel_trace,
                    scenario_path=scenario_path,
                    workflow_id=workflow_id,
                    timeout_seconds=trace_timeout_seconds,
                    require_submission=workflow_advanced,
                )
            except Exception:
                if respond_error is not None:
                    raise respond_error
                raise
            run_dir = output_dir / scenario_id / workflow_id
            common_trace_path = run_dir / "common.yaml"
            write_yaml(common_trace_path, common_trace)
            evaluation = evaluate_common_trace(scenario, common_trace)
            outcome = "PASS" if evaluation.passed else "FAIL"
            print(
                f"RUN {attempt}: {workflow_id} | "
                f"{before_id} -> {after_id or after.get('status', 'not awaiting')} | "
                f"{outcome}"
            )
        except Exception as error:  # noqa: BLE001 - keep repeated eval runs going
            execution_error = f"{type(error).__name__}: {error}"
            print(f"RUN {attempt}: {workflow_id} | ERROR {execution_error}")
        finally:
            if handle is not None:
                try:
                    await handle.terminate("checkpoint evaluation complete")
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    pass
            if agent is not None:
                await agent.close()

        return TargetedRunResult(
            attempt=attempt,
            scenario_id=scenario_id,
            workflow_id=workflow_id,
            common_trace_path=common_trace_path,
            evaluation=evaluation,
            execution_error=execution_error,
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )


async def run(args: argparse.Namespace) -> int:
    scenario_case = load_scenario_case(args.scenario)
    scenario = scenario_case.scenario
    checkpoint = scenario_case.checkpoint
    fixture = scenario_case.conversation
    scenario_path = scenario_case.scenario_path
    process_id, state_id = scenario_case.target
    definition = load_document(args.definition)

    if definition["id"] != scenario["journey_id"]:
        raise ValueError("Scenario journey_id does not match workflow definition")

    current_state = definition["processes"][process_id]["states"][state_id]
    initial_messages, current_user_message = agent_input(
        fixture, current_state["prompt"]
    )

    batch_id = args.batch_id or new_batch_id()
    batch_dir = args.batch_output_dir / batch_id
    if batch_dir.exists():
        raise ValueError(f"Batch output already exists: {batch_dir}")
    batch_dir.mkdir(parents=True)
    results_path = batch_dir / "results.jsonl"
    results_path.write_text("", encoding="utf-8")
    started_at = datetime.now(UTC)
    write_json(
        batch_dir / "batch.json",
        {
            "schema_version": "0.1",
            "batch_id": batch_id,
            "started_at": started_at.isoformat(),
            "scenario_id": scenario["id"],
            "scenario_path": str(scenario_path),
            "repeat": args.repeat,
            "concurrency": args.concurrency,
            "model_id": args.model_id,
            "otel_trace": str(args.otel_trace),
        },
    )

    temporal_client = await Client.connect(args.temporal_address)
    semaphore = asyncio.Semaphore(min(args.repeat, args.concurrency))
    results = await asyncio.gather(
        *[
            run_once(
                attempt,
                scenario=scenario,
                scenario_path=scenario_path,
                definition=definition,
                checkpoint=checkpoint,
                initial_messages=initial_messages,
                current_user_message=current_user_message,
                temporal_client=temporal_client,
                temporal_address=args.temporal_address,
                task_queue=args.task_queue,
                workflow_server_url=args.workflow_server_url,
                model_id=args.model_id,
                region=args.region,
                otel_trace=args.otel_trace,
                output_dir=args.output_dir,
                trace_timeout_seconds=args.trace_timeout_seconds,
                semaphore=semaphore,
            )
            for attempt in range(1, args.repeat + 1)
        ]
    )

    counts = {"pass": 0, "fail": 0, "error": 0}
    for result in results:
        run_dir = args.output_dir / result.scenario_id / result.workflow_id
        evaluation_path = run_dir / "evaluation.json"
        record = evaluation_record(
            result,
            batch_id=batch_id,
            scenario_path=scenario_path,
            model_id=args.model_id,
            otel_trace=args.otel_trace,
            evaluation_path=evaluation_path,
        )
        write_json(evaluation_path, record)
        append_jsonl(results_path, record)
        counts[result.outcome] += 1

    completed_at = datetime.now(UTC)
    summary_path = batch_dir / "summary.json"
    write_json(
        summary_path,
        {
            "schema_version": "0.1",
            "batch_id": batch_id,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_ms": round(
                (completed_at - started_at).total_seconds() * 1000,
                3,
            ),
            "scenario_id": scenario["id"],
            "model_id": args.model_id,
            "total": len(results),
            "passed": counts["pass"],
            "failed": counts["fail"],
            "errors": counts["error"],
            "results": str(results_path),
        },
    )

    print(
        f"\n{len(results)} runs: {counts['pass']} passed, "
        f"{counts['fail']} failed, {counts['error']} errors."
    )
    print(f"batch results: {results_path}")
    print(f"batch summary: {summary_path}")
    return 0 if counts["fail"] == 0 and counts["error"] == 0 else 1


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a self-contained durable evaluation scenario case."
    )
    parser.add_argument(
        "scenario",
        type=Path,
        help=(
            "Scenario case directory or path relative to evaluation/scenarios, "
            "for example maternity_allowance/work_status_fixed_term_contract_ended"
        ),
    )
    parser.add_argument("--repeat", type=positive_int, default=1)
    parser.add_argument("--concurrency", type=positive_int, default=1)
    parser.add_argument("--definition", type=Path, default=DEFAULT_DEFINITION)
    parser.add_argument(
        "--otel-trace",
        type=Path,
        default=Path(os.environ.get("OTEL_EXPORT_FILE", DEFAULT_OTEL_TRACE)),
        help="Worker OTEL JSONL file (default: OTEL_EXPORT_FILE or .traces/durable-otel.jsonl)",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--batch-output-dir",
        type=Path,
        default=DEFAULT_BATCH_OUTPUT_DIR,
    )
    parser.add_argument("--batch-id")
    parser.add_argument(
        "--trace-timeout-seconds",
        type=float,
        default=DEFAULT_TRACE_TIMEOUT_SECONDS,
        help="How long to wait for the worker to export the completed InputState span",
    )
    parser.add_argument(
        "--model-id",
        default=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6"),
    )
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-west-2"))
    parser.add_argument(
        "--temporal-address",
        default=os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
    )
    parser.add_argument(
        "--task-queue", default=os.environ.get("TEMPORAL_TASK_QUEUE", "sfsm-queue")
    )
    parser.add_argument(
        "--workflow-server-url",
        default=os.environ.get("WORKFLOW_SERVER_URL", "http://localhost:8080"),
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
