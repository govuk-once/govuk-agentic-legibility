"""Integration tests for the FSM workflow executor and update validator."""

import json
from pathlib import Path
from typing import Any
import shutil

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.client import WorkflowUpdateFailedError

from src.activities import CallParams, NotifyParams, activity
from src.context import InputSubmission
from src.interpreter import SFSMInterpreter

TEMPORAL_PATH = shutil.which("temporal")


# Provide mock activities that don't hit the network
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
                        "dateOfBirth": "1990-01-01",
                        "email": "jane@example.com",
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


@pytest.fixture
def subprocess_workflow_def() -> dict[str, Any]:
    return {
        "schema": "sfsm/0.2",
        "id": "test.subprocess_stack",
        "version": "1.0",
        "entry": "main",
        "executor": {},
        "processes": {
            "main": {
                "start": "call_sub",
                "vars": {"child_result": None},
                "states": {
                    "call_sub": {
                        "type": "invoke",
                        "process": "child_proc",
                        "input": {"val": "hello"},
                        "assign": "child_result",
                        "next": "end_main",
                    },
                    "end_main": {
                        "type": "end",
                        "status": "success",
                        "return": {"output": {"$": "child_result"}},
                    },
                },
            },
            "child_proc": {
                "start": "ask_child_input",
                "vars": {},
                "states": {
                    "ask_child_input": {
                        "type": "input",
                        "prompt": "Child prompt?",
                        "schema": {"kind": "string"},
                        "assign": "child_var",
                        "next": "end_child",
                    },
                    "end_child": {
                        "type": "end",
                        "status": "success",
                        "outcome": "completed",
                        "return": {"echo": {"$": "child_var"}},
                    },
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_workflow_execution_completes(
    sample_workflow_def: dict[str, Any],
) -> None:
    """Workflow executes input states, evaluates choice rules, and returns final payload."""
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
                id="test-wf",
                task_queue="test-q",
            )

            # Wait for workflow to hit the first input state
            await env.sleep(0.1)

            awaiting = await handle.query("awaiting")
            assert awaiting is not None
            assert awaiting["prompt"] == "What is your name?"

            # Submit string for the name
            await handle.execute_update(
                "submit_input", InputSubmission(token=awaiting["token"], value="Alice")
            )

            # Wait for the workflow to transition to the second input state
            await env.sleep(0.1)

            awaiting = await handle.query("awaiting")
            assert awaiting is not None
            assert awaiting["prompt"] == "Do you want to receive weather alerts?"

            # Submit boolean for the subscription
            await handle.execute_update(
                "submit_input", InputSubmission(token=awaiting["token"], value=True)
            )

            # Workflow should now complete and return the projected data
            result = await handle.result()
            assert result["status"] == "success"
            assert result["return"] == {"name": "Alice", "status": "subscribed"}


@pytest.mark.asyncio
async def test_update_validator_rejects_stale_token(
    sample_workflow_def: dict[str, Any],
) -> None:
    """The update validator rejects updates with mismatched token parameters."""
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
                id="test-wf-2",
                task_queue="test-q",
            )
            await env.sleep(0.1)

            with pytest.raises(WorkflowUpdateFailedError) as excinfo:
                # Provide string "Alice" to match the first schema if it bypassed the token check
                await handle.execute_update(
                    "submit_input", InputSubmission(token="wrong_token", value="Alice")
                )

            # The validator error is nested in the 'cause' of the WorkflowUpdateFailedError
            assert "Token mismatch" in str(excinfo.value.cause)


@pytest.mark.asyncio
async def test_update_validator_rejects_invalid_kind_type(
    sample_workflow_def: dict[str, Any],
) -> None:
    """The update validator rejects submissions that violate schema kind types."""
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
                id="test-wf-type-check",
                task_queue="test-q",
            )
            await env.sleep(0.1)

            awaiting = await handle.query("awaiting")
            assert awaiting["schema"]["kind"] == "string"

            # First submit valid string to reach boolean prompt
            await handle.execute_update(
                "submit_input", InputSubmission(token=awaiting["token"], value="Alice")
            )
            await env.sleep(0.1)

            awaiting = await handle.query("awaiting")
            assert awaiting["schema"]["kind"] == "boolean"

            # Submit string "Yes" instead of boolean True -> validator must reject
            with pytest.raises(WorkflowUpdateFailedError) as excinfo:
                await handle.execute_update(
                    "submit_input",
                    InputSubmission(token=awaiting["token"], value="Yes"),
                )

            assert "Expected boolean" in str(excinfo.value.cause)


@pytest.mark.asyncio
async def test_subprocess_stack_invocation(
    subprocess_workflow_def: dict[str, Any],
) -> None:
    """Engine executes sub-processes using stack frames and maps outputs back to parent context."""
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
                subprocess_workflow_def,
                id="test-wf-subprocess",
                task_queue="test-q",
            )
            await env.sleep(0.1)

            awaiting = await handle.query("awaiting")
            assert awaiting["prompt"] == "Child prompt?"

            await handle.execute_update(
                "submit_input", InputSubmission(token=awaiting["token"], value="world")
            )

            result = await handle.result()
            assert result["status"] == "success"
            assert result["return"] == {"output": {"echo": "world"}}
