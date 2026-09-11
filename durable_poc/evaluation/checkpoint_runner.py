"""Run one targeted durable-workflow interaction repeatedly against the real agent."""

from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from temporalio.client import Client

from agent.agent import WorkflowAgent
from src.context import InterpreterState, StackFrame
from src.interpreter import SFSMInterpreter

DURABLE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DURABLE_ROOT.parent
DEFAULT_DEFINITION = DURABLE_ROOT / "dwp_ma1_schema.json"
DEFAULT_FIXTURES = REPO_ROOT / "agents" / "src" / "evaluation" / "fixtures"


def load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    value = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_fixture(fixture_id: str, version: str, directory: Path) -> dict[str, Any]:
    for path in directory.glob("*.json"):
        fixture = load_document(path)
        if fixture.get("id") == fixture_id and fixture.get("version") == version:
            return fixture
    raise ValueError(f"Fixture {fixture_id!r} version {version!r} not found")


def build_checkpoint_state(
    definition: dict[str, Any], checkpoint: dict[str, Any]
) -> InterpreterState:
    process_id = checkpoint["process_id"]
    state_id = checkpoint["state_id"]
    process = definition["processes"][process_id]
    state = process["states"][state_id]
    if state.get("type") != "input":
        raise ValueError(f"Checkpoint {process_id}.{state_id} is not an input state")

    variables = deepcopy(process.get("vars", {}))
    variables.update(deepcopy(checkpoint.get("vars", {})))
    if "input" in checkpoint:
        variables["input"] = deepcopy(checkpoint["input"])

    return InterpreterState(
        frames=[StackFrame(process_id=process_id, state_id=state_id, vars=variables)],
        step_counter=checkpoint.get("step_counter", 0),
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


async def run_once(
    attempt: int,
    *,
    scenario_id: str,
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
    semaphore: asyncio.Semaphore,
) -> str | None:
    async with semaphore:
        workflow_id = f"eval-{scenario_id}-{uuid4().hex[:8]}"
        handle = None
        agent = None
        try:
            handle = await temporal_client.start_workflow(
                SFSMInterpreter.run,
                args=[definition, build_checkpoint_state(definition, checkpoint)],
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
            await agent.respond(current_user_message, context=before)

            after = agent.session_state or {}
            awaiting = after.get("awaiting")
            after_id = awaiting.get("state_id") if isinstance(awaiting, dict) else None
            print(
                f"RUN {attempt}: {workflow_id} | "
                f"{before_id} -> {after_id or after.get('status', 'not awaiting')}"
            )
            return None
        except Exception as error:  # noqa: BLE001 - keep repeated smoke runs going
            message = f"{type(error).__name__}: {error}"
            print(f"RUN {attempt}: ERROR {message}")
            return message
        finally:
            if handle is not None:
                try:
                    await handle.terminate("checkpoint evaluation complete")
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    pass
            if agent is not None:
                await agent.close()


async def run(args: argparse.Namespace) -> int:
    scenario = load_document(args.scenario)
    scenario_input = scenario["input"]
    checkpoint = scenario_input["checkpoint"]
    fixture_ref = scenario_input["conversation_fixture"]
    fixture = load_fixture(fixture_ref["id"], fixture_ref["version"], args.fixture_dir)
    definition = load_document(args.definition)

    if definition["id"] != scenario["journey_id"]:
        raise ValueError("Scenario journey_id does not match workflow definition")
    if fixture["journey_id"] != scenario["journey_id"]:
        raise ValueError("Fixture journey_id does not match scenario")

    current_state = definition["processes"][checkpoint["process_id"]]["states"][
        checkpoint["state_id"]
    ]
    initial_messages, current_user_message = agent_input(
        fixture, current_state["prompt"]
    )

    temporal_client = await Client.connect(args.temporal_address)
    semaphore = asyncio.Semaphore(min(args.repeat, args.concurrency))
    errors = await asyncio.gather(
        *[
            run_once(
                attempt,
                scenario_id=scenario["id"],
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
                semaphore=semaphore,
            )
            for attempt in range(1, args.repeat + 1)
        ]
    )
    error_count = sum(error is not None for error in errors)
    print(f"\n{args.repeat} runs completed; {error_count} execution error(s).")
    print("No semantic pass/fail scoring is performed yet.")
    return 1 if error_count else 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--repeat", type=positive_int, default=1)
    parser.add_argument("--concurrency", type=positive_int, default=1)
    parser.add_argument("--definition", type=Path, default=DEFAULT_DEFINITION)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURES)
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
