"""
Run a BPMN workflow from the command line.
"""

import asyncio
import json
import mimetypes
import uuid
from pathlib import Path

from temporalio.client import Client

from bpmn.temporal_engine.bpmn_interpreter import (
    BPMNInterpreter,
)
from bpmn.temporal_engine.bpmn_parser import (
    parse_bpmn_file,
)

TASK_QUEUE = "bpmn-queue"


def collect_file_metadata(
    file_path: str,
) -> dict[str, object]:
    """
    Validate a file path and return
    workflow-safe file metadata.

    The file contents are not loaded
    into workflow state. Only metadata
    is stored.
    """

    path = Path(file_path).expanduser()

    if not path.exists():
        raise ValueError(f"File does not exist: {path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    content_type, _ = mimetypes.guess_type(
        str(path),
    )

    return {
        "path": str(
            path.resolve(),
        ),
        "name": path.name,
        "bytes": path.stat().st_size,
        "content_type": (content_type or "application/octet-stream"),
    }


async def main() -> None:

    definition = parse_bpmn_file(
        "change_of_address.bpmn",
    )

    workflow_id = f"{definition.id}_{uuid.uuid4().hex[:8]}"

    client = await Client.connect(
        "localhost:7233",
    )

    handle = await client.start_workflow(
        BPMNInterpreter.run,
        definition.model_dump(
            by_alias=True,
        ),
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    print()
    print("Started workflow")
    print(f"Workflow ID: {workflow_id}")
    print()

    last_step = 0
    awaiting_token = None

    while True:
        #
        # Print activity history.
        #
        try:
            history = await handle.query(
                BPMNInterpreter.get_activity_history,
            )

            for activity in history:
                step = activity.get(
                    "step",
                    0,
                )

                if step <= last_step:
                    continue

                print()
                print("=" * 60)

                print(
                    f"[Step {step}] "
                    f"[{activity.get('type', 'Unknown')}] "
                    f"{activity.get('name') or activity.get('id')}"
                )

                print(f"Node ID: {activity.get('id')}")

                if activity.get("process_id"):
                    print(f"Process: {activity['process_id']}")

                print("=" * 60)
                print()

                last_step = step

        except Exception:
            pass

        awaiting = await handle.query(
            BPMNInterpreter.awaiting,
        )

        if awaiting:
            #
            # Prevent duplicate prompts.
            #
            if awaiting.token == awaiting_token:
                await asyncio.sleep(
                    0.5,
                )

                continue

            awaiting_token = awaiting.token

            task_id = awaiting.state_id
            prompt = awaiting.prompt
            token = awaiting.token

            print("-" * 60)

            print(f"Task: {task_id}")

            print("-" * 60)

            schema = awaiting.schema

            payload = {}

            fields = schema.get(
                "fields",
                [],
            )

            #
            # Form task.
            #
            if fields:
                print()

                print(
                    schema.get(
                        "title",
                        prompt,
                    )
                )

                print()

                for field in fields:
                    label = field.get(
                        "label",
                        field["id"],
                    )

                    field_type = field.get(
                        "type",
                        "string",
                    )

                    while True:
                        value = input(f"{label}: ").strip()

                        try:
                            if field_type == "file":
                                payload[field["id"]] = collect_file_metadata(
                                    value,
                                )

                            else:
                                payload[field["id"]] = value

                            break

                        except ValueError as exc:
                            print()
                            print("Validation error:")
                            print(exc)
                            print("Please try again.")
                            print()

            #
            # Manual task.
            #
            else:
                print()

                input("Press Enter to continue...")

                payload = {}

            await handle.execute_update(
                BPMNInterpreter.submit_input,
                {
                    "token": token,
                    "value": payload,
                },
            )

            awaiting_token = None

            continue

        try:
            result = await asyncio.wait_for(
                handle.result(),
                timeout=1,
            )

            print()
            print("=" * 60)
            print("WORKFLOW COMPLETE")
            print("=" * 60)
            print()

            print(
                json.dumps(
                    result,
                    indent=2,
                )
            )

            break

        except asyncio.TimeoutError:
            pass

        await asyncio.sleep(
            0.5,
        )


if __name__ == "__main__":
    asyncio.run(main())
