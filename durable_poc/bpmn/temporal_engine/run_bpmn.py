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
from bpmn.temporal_engine.context import (
    InputSubmission,
)
from bpmn.temporal_engine.bpmn_parser import (
    parse_bpmn_file,
)
from bpmn.temporal_engine.bpmn_model import (
    BPMNDefinition,
)

TASK_QUEUE = "bpmn-queue"

def load_process_set(
    entry_bpmn: str,
    child_bpmns: list[str],
) -> BPMNDefinition:
    """
    Load a BPMN application consisting of
    one root process and multiple callable
    subprocess BPMNs.
    """

    definition = parse_bpmn_file(
        entry_bpmn,
    )

    for bpmn_file in child_bpmns:

        child_definition = parse_bpmn_file(
            bpmn_file,
        )

        #
        # Merge processes.
        #

        duplicate_processes = (
            set(definition.processes)
            & set(child_definition.processes)
        )

        if duplicate_processes:
            raise ValueError(
                f"Duplicate process ids found: "
                f"{sorted(duplicate_processes)}"
            )

        definition.processes.update(
            child_definition.processes,
        )

        #
        # Merge BPMN errors.
        #

        definition.errors.update(
            child_definition.errors,
        )

    return definition


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

def resolve_dynamic_options(
    variables: dict,
    variable_name: str,
) -> list:

    value = variables.get(
        variable_name,
    )

    if isinstance(
        value,
        list,
    ):
        return value

    return []


async def main() -> None:

    definition = load_process_set(
        entry_bpmn="change_of_address.bpmn",
        child_bpmns=[
            "confirm_intent.bpmn",
            "name_change_check.bpmn",
            "driver_lookup.bpmn",
            "photo_update.bpmn",
            "signature_update.bpmn",
            "organ_donation.bpmn",
            "address_selection.bpmn",
            "address_update.bpmn",
            "finalisation.bpmn",
        ],
    )

    print()
    print("Loaded processes:")

    for process_id in definition.processes:
        print(f" - {process_id}")

    print()

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
        workflow_vars = await handle.query(
            BPMNInterpreter.current_variables,
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

            if hasattr(schema, "model_dump"):
                schema = schema.model_dump()

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

                    options = field.get(
                        "options",
                        [],
                    )

                    source_variable = field.get(
                        "source_variable",
                    )

                    dynamic_options = []

                    if source_variable:
                        dynamic_options = resolve_dynamic_options(
                            workflow_vars,
                            source_variable,
                        )

                    #
                    # Render choices BEFORE prompting
                    #

                    if options:
                        print()
                        print(label)

                        for option in options:
                            print(
                                f" - {option['value']}: "
                                f"{option['label']}"
                            )

                    if dynamic_options:

                        print()

                        print(label)

                        for idx, option in enumerate(
                            dynamic_options,
                            start=1,
                        ):
                            print(
                                f" [{idx}] "
                                f"{option.get('single_line', option)}"
                            )

                    field_type = field.get(
                        "type",
                        "string",
                    )

                    while True:
                        value = input(f"{label}: ").strip()

                        #
                        # Dynamic choices
                        #
                        if dynamic_options:

                            if value.isdigit():

                                idx = int(value) - 1

                                if 0 <= idx < len(dynamic_options):

                                    payload[field["id"]] = (
                                        dynamic_options[idx]
                                    )

                                    break

                            print(
                                f"Choose a value between "
                                f"1 and {len(dynamic_options)}"
                            )

                            continue

                

                        #
                        # Static choices
                        #
                        if options:
                            valid_values = {
                                str(o["value"])
                                for o in options
                            }

                            if value not in valid_values:
                                print(
                                    f"Choose one of: "
                                    f"{', '.join(sorted(valid_values))}"
                                )
                                continue


                        try:
                            if field_type == "file":
                                payload[field["id"]] = collect_file_metadata(
                                    value,
                                )

                            elif field_type == "boolean":
                                payload[field["id"]] = (
                                    value.lower() in {
                                        "true",
                                        "yes",
                                        "y",
                                        "1",
                                    }
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
                InputSubmission(
                    token=token,
                    value=payload,
                ),
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
