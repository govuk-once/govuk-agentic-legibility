"""
Run a BPMN workflow from the command line.
"""

import asyncio
import json
import mimetypes
import uuid
from pathlib import Path
import logging

from temporalio.client import Client

from bpmn.temporal_engine.bpmn_interpreter import (
    BPMNInterpreter,
)
from bpmn.temporal_engine.context import (
    InputSubmission,
)
from bpmn.temporal_engine.paths import (
    resolve_path,
)
from bpmn.temporal_engine.bpmn_parser import (
    parse_bpmn_file,
)

logger = logging.getLogger(__name__)

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

    definition = parse_bpmn_file(
        "bpmn/change_of_address.bpmn",
    )

    definition.process_registry = {
        "confirm_intent": "confirm_intent.bpmn",
        "name_change_check": "name_change_check.bpmn",
        "driver_lookup": "driver_lookup.bpmn",
        "photo_update": "photo_update.bpmn",
        "signature_update": "signature_update.bpmn",
        "organ_donation": "organ_donation.bpmn",
        "address_selection": "address_selection.bpmn",
        "address_update": "address_update.bpmn",
        "finalisation": "finalisation.bpmn",
    }

    logger.info(
        "Loaded BPMN definition '%s' with %s processes",
        definition.id,
        len(definition.processes),
    )

    for process in definition.processes.values():

        logger.info(
            "Process %s contains %s nodes and %s flows",
            process.id,
            len(process.nodes),
            len(process.flows),
        )

        for flow in process.flows.values():
            logger.info(
                "Flow %s: %s -> %s",
                flow.id,
                flow.source_ref,
                flow.target_ref,
            )

    for process in definition.processes.values():

        logger.info(
            "Checking boundary event routing in process %s",
            process.id,
        )

        for node in process.nodes.values():

            if getattr(node, "type", None) == "boundaryEvent":

                outgoing = process.outgoing_flows(
                    node.id,
                )

                logger.info(
                    "Boundary %s -> %s",
                    node.id,
                    [
                        f.target_ref
                        for f in outgoing
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

                if activity.get("type") == "SendTask":

                    title = activity.get("title")
                    text = activity.get("text")

                    if title:
                        print()
                        print(title)

                    if text:
                        print()
                        print(text)

                if activity.get("process_id"):
                    print(f"Process: {activity['process_id']}")

                print("=" * 60)
                print()

                last_step = step

        except Exception as exc:
            logger.debug(
                "History query failed: %s",
                exc,
            )

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

                    if field_type == "display":
                        source_variable = field.get(
                            "source_variable"
                        )

                        value = resolve_path(
                            workflow_vars,
                            source_variable,
                        )

                        print(
                            f"{label}: {value}"
                        )

                        continue

                    while True:

                        value = input(
                            f"{label}: "
                        ).strip()

                        if field.get(
                            "required",
                            False,
                        ) and not value:

                            print(
                                f"{label} is required."
                            )

                            continue

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

                                if value.lower() not in {
                                    "true",
                                    "false",
                                    "yes",
                                    "no",
                                    "y",
                                    "n",
                                    "1",
                                    "0",
                                }:
                                    print(
                                        "Please enter yes or no."
                                    )
                                    continue

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

    # logging.basicConfig(
    #     level=logging.INFO,
    #     format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    # )

    asyncio.run(main())
