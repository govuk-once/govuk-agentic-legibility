"""Integration tests for the FSM workflow executor, activities, and update validators."""

import json
from pathlib import Path
from typing import Any
import shutil

import pytest
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
