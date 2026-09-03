"""Interactive terminal CLI for the FSM workflow."""

import asyncio
import json
import os
from pathlib import Path

from temporalio.client import Client, WorkflowExecutionStatus
from src.context import InputSubmission


async def main() -> None:
    # Connect to standard local Temporal server
    print("Connecting to server...")
    client = await Client.connect("localhost:7233")

    # Load your schema (assuming it's saved as workflow.json)
    print("Loading definition...")
    file_path = Path(f"{os.getcwd()}/dwp_ma1_schema.json")
    with open(file_path, "r") as f:
        definition = json.load(f)

    # Patch long timeouts for human interaction
    print("Patching time intervals...")
    if "finalisation" in definition.get("processes", {}):
        definition["processes"]["finalisation"]["vars"]["poll_interval"] = "PT2S"
        definition["processes"]["finalisation"]["vars"]["delivery_wait"] = "PT15S"
        definition["processes"]["finalisation"]["vars"]["reminder_after"] = "PT10S"

    definition.setdefault("vars", {})["env"] = {
        "dvla_base": "http://localhost:8000/app/photo",
        "postoffice_base": "http://localhost:8000/app/postoffice",
    }

    print("Starting Workflow...")

    # Start the workflow
    handle = await client.start_workflow(
        "SFSMInterpreter",
        args=[definition, None],
        id="interactive-demo",
        task_queue="sfsm-queue",
    )

    print("Workflow started...")
    printed_transcript_len = 0

    while True:
        # 1. Check if the workflow has finished
        description = await handle.describe()
        if description.status != WorkflowExecutionStatus.RUNNING:
            # Drain remaining transcript entries before exiting
            transcript = await handle.query("transcript")
            if len(transcript) > printed_transcript_len:
                for entry in transcript[printed_transcript_len:]:
                    print(f"\n📩 [Message]: {entry['message']}")

            result = await handle.result()
            print("\n✅ Workflow Complete!")
            print(f"Outcome: {result}")
            break

        # 2. Print any new transcript messages
        transcript = await handle.query("transcript")
        if len(transcript) > printed_transcript_len:
            for entry in transcript[printed_transcript_len:]:
                print(f"\n📩 [Message]: {entry['message']}")
            printed_transcript_len = len(transcript)

        # 3. Check if the workflow is waiting for input
        awaiting = await handle.query("awaiting")

        if awaiting:
            schema = (
                awaiting.schema if hasattr(awaiting, "schema") else awaiting["schema"]
            )
            prompt = (
                awaiting.prompt if hasattr(awaiting, "prompt") else awaiting["prompt"]
            )
            token = awaiting.token if hasattr(awaiting, "token") else awaiting["token"]
            options = (
                awaiting.options
                if hasattr(awaiting, "options")
                else awaiting.get("options")
            )
            timeout_sec = (
                awaiting.timeout_seconds
                if hasattr(awaiting, "timeout_seconds")
                else awaiting.get("timeout_seconds")
            )

            kind = (
                schema.get("kind")
                if isinstance(schema, dict)
                else getattr(schema, "kind", None)
            )

            print(f"\n🔵 {prompt}")

            # Safe option key extractor helper
            def get_opt_val(opt, preferred_key=None):
                if isinstance(opt, dict):
                    if preferred_key and preferred_key in opt:
                        return opt[preferred_key]
                    return opt.get("value") or opt.get("id") or str(opt)
                return getattr(opt, "value", getattr(opt, "id", str(opt)))

            def get_opt_label(opt, preferred_key=None):
                if isinstance(opt, dict):
                    if preferred_key and preferred_key in opt:
                        return opt[preferred_key]
                    return opt.get("label") or opt.get("name") or str(opt)
                return getattr(opt, "label", getattr(opt, "name", str(opt)))

            # If it's a select list, render the options with 1-based indexing
            if kind in ["select_one", "select_many"] and options:
                v_key = schema.get("value_key") if isinstance(schema, dict) else getattr(schema, "value_key", None)
                l_key = schema.get("label_key") if isinstance(schema, dict) else getattr(schema, "label_key", None)
                for idx, opt in enumerate(options, 1):
                    o_lbl = get_opt_label(opt, l_key)
                    print(f"   [{idx}] {o_lbl}")

            # Non-blocking input if workflow provided timeout_seconds, else standard blocking input
            raw_val = None
            if timeout_sec:
                try:
                    raw_val = await asyncio.wait_for(
                        asyncio.to_thread(input, "> "), timeout=timeout_sec + 0.5
                    )
                except asyncio.TimeoutError:
                    print("\n⌛ Input timed out waiting for user response...")
                    await asyncio.sleep(1)
                    continue
            else:
                raw_val = input("> ")

            val = None

            if kind == "boolean":
                val = raw_val.strip().lower() in ["y", "yes", "true", "1"]
            elif kind == "file_ref":
                path = raw_val.strip()
                content_type = (
                    "image/png" if path.lower().endswith(".png") else "image/jpeg"
                )
                val = {
                    "ref": path,
                    "content_type": content_type,
                    "bytes": os.path.getsize(path) if os.path.exists(path) else 1024,
                }
            elif kind == "select_one" and options:
                raw_str = raw_val.strip()
                v_key = schema.get("value_key") if isinstance(schema, dict) else getattr(schema, "value_key", None)

                selected_opt = None

                # 1. Check if user typed a 1-based index (e.g. '1' for option 1)
                if raw_str.isdigit():
                    idx = int(raw_str) - 1
                    if 0 <= idx < len(options):
                        selected_opt = options[idx]

                # 2. Check match by option value
                if not selected_opt:
                    for opt in options:
                        if str(get_opt_val(opt, v_key)) == raw_str:
                            selected_opt = opt
                            break

                if selected_opt:
                    if v_key in ["uprn", "single_line"]:
                        val = selected_opt
                    else:
                        val = get_opt_val(selected_opt, v_key)
                else:
                    val = raw_str

            elif kind == "select_many" and options:
                # Handle comma-separated selections like '1, 2'
                raw_items = [i.strip() for i in raw_val.strip().split(",") if i.strip()]
                val = []
                v_key = schema.get("value_key") if isinstance(schema, dict) else getattr(schema, "value_key", None)

                for raw_str in raw_items:
                    selected_opt = None
                    if raw_str.isdigit():
                        idx = int(raw_str) - 1
                        if 0 <= idx < len(options):
                            selected_opt = options[idx]

                    if not selected_opt:
                        for opt in options:
                            if str(get_opt_val(opt, v_key)) == raw_str:
                                selected_opt = opt
                                break

                    if selected_opt:
                        val.append(get_opt_val(selected_opt, v_key))
                    else:
                        val.append(raw_str)
            else:
                val = raw_val.strip()

            print("Submitting...")
            try:
                await handle.execute_update(
                    "submit_input", InputSubmission(token=token, value=val)
                )
            except Exception as e:
                # E.g., validation errors returned synchronously from the update validator
                print(f"❌ Input rejected: {e}")

        else:
            # Workflow is busy processing an activity or waiting on a timer
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo terminated.")
