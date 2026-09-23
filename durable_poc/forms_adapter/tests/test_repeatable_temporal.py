"""Opt-in real Temporal regression for repeatable Forms (requires Temporal CLI)."""

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("temporalio")
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from forms_adapter import compile_form
from src.context import InputSubmission
from src.interpreter import SFSMInterpreter

TEMPORAL_PATH = shutil.which("temporal")
FIXTURE = Path(__file__).parent / "fixtures" / "repeatable.json"


@pytest.mark.asyncio
@pytest.mark.skipif(TEMPORAL_PATH is None, reason="Temporal CLI not installed")
async def test_repeatable_inputs_have_new_tokens_and_accumulate_on_real_temporal():
    definition = compile_form(json.loads(FIXTURE.read_text(encoding="utf-8")))
    definition["processes"]["main"]["states"]["end_form"]["return"] = {"$": "answers"}

    async with await WorkflowEnvironment.start_local(dev_server_existing_path=TEMPORAL_PATH) as env:
        async with Worker(env.client, task_queue="repeatable-q", workflows=[SFSMInterpreter]):
            handle = await env.client.start_workflow(
                SFSMInterpreter.run, definition, id="repeatable-form-test", task_queue="repeatable-q"
            )

            async def submit(expected_state, value):
                for _ in range(40):
                    awaiting = await handle.query("awaiting")
                    if awaiting and awaiting["state_id"] == expected_state:
                        await handle.execute_update(
                            "submit_input", InputSubmission(token=awaiting["token"], value=value)
                        )
                        return awaiting["token"]
                    await env.sleep(0.05)
                pytest.fail(f"Timed out awaiting {expected_state}")

            token1 = await submit("site", "1 Alpha Road, London")
            await submit("site__more", True)
            token2 = await submit("site", "2 Beta Road, Leeds")
            assert token2 != token1
            await submit("site__more", False)
            snapshot = await handle.query("evaluation_checkpoint")
            assert snapshot["frames"][0]["vars"]["answers"]["site"] == [
                "1 Alpha Road, London", "2 Beta Road, Leeds"
            ]
            await submit("count", "42")
            result = await handle.result()
            assert result["return"]["site"] == ["1 Alpha Road, London", "2 Beta Road, Leeds"]


@pytest.mark.asyncio
@pytest.mark.skipif(TEMPORAL_PATH is None, reason="Temporal CLI not installed")
async def test_optional_repeatable_skip_after_revisit_keeps_answers_and_refreshes_token():
    # Opt-in: uses the *same* Temporal interpreter and its input-token updates.
    definition = json.loads((FIXTURE.parent / "optional_repeatable.json").read_text(encoding="utf-8"))
    definition = compile_form(definition)
    definition["processes"]["main"]["states"]["end_form"]["return"] = {"$": "answers"}

    async with await WorkflowEnvironment.start_local(dev_server_existing_path=TEMPORAL_PATH) as env:
        async with Worker(env.client, task_queue="optional-repeatable-q", workflows=[SFSMInterpreter]):
            handle = await env.client.start_workflow(
                SFSMInterpreter.run, definition,
                id="optional-repeatable-form-test", task_queue="optional-repeatable-q"
            )

            async def submit(expected_state, value):
                for _ in range(40):
                    awaiting = await handle.query("awaiting")
                    if awaiting and awaiting["state_id"] == expected_state:
                        await handle.execute_update(
                            "submit_input", InputSubmission(token=awaiting["token"], value=value)
                        )
                        return awaiting["token"]
                    await env.sleep(0.05)
                pytest.fail(f"Timed out awaiting {expected_state}")

            token1 = await submit("site", "Acme Ltd")
            await submit("site__more", True)
            token2 = await submit("site", "")  # Skip on second visit; never append it.
            assert token2 != token1
            for _ in range(40):
                awaiting = await handle.query("awaiting")
                if awaiting and awaiting["state_id"] == "count":
                    break
                await env.sleep(0.05)
            else:
                pytest.fail("Skipped repeat did not reach the original next question")
            snapshot = await handle.query("evaluation_checkpoint")
            assert snapshot["frames"][0]["state_id"] == "count"
            assert snapshot["frames"][0]["vars"]["answers"]["site"] == ["Acme Ltd"]
            await submit("count", "42")
            result = await handle.result()
            assert result["return"]["site"] == ["Acme Ltd"]
