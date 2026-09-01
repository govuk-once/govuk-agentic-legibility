"""Command-line interface for the generic server-driven journey executor."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

from agents.src.workflow_executor.client import JourneyClient
from agents.src.workflow_executor.config import (
    load_executor_environment,
    resolve_base_url,
)
from agents.src.workflow_executor.executor import JourneyExecutor
from agents.src.workflow_executor.input_provider import JsonCliInputProvider
from agents.src.workflow_executor.state import load_response, save_response
from agents.src.workflow_executor.trace import JsonlTraceRecorder
from agents.src.workflow_executor.types import JsonObject, ReadOnlyJsonObject

ResponseObserver = Callable[[ReadOnlyJsonObject], None]


def build_parser() -> argparse.ArgumentParser:
    """Create the workflow-executor argument parser.

    Returns:
        The configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Execute a server-driven service journey using JSON input.",
    )
    parser.add_argument(
        "journey_id",
        nargs="?",
        help="Journey identifier advertised by the service catalogue.",
    )
    parser.add_argument(
        "--base-url",
        help="Journey service URL, for example http://127.0.0.1:8000.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        help="Save the latest service response after every transition.",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="Resume from a response previously saved with --state-file.",
    )
    parser.add_argument(
        "--max-interactions",
        type=int,
        help="Suspend after processing this many interactions.",
    )
    parser.add_argument(
        "--trace-dir",
        type=Path,
        help="Write a local JSONL trace for this run.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the workflow-executor CLI.

    Args:
        argv: Optional command-line arguments for tests or embedding.

    Returns:
        Process exit status.
    """
    load_executor_environment()
    args = build_parser().parse_args(argv)
    if args.resume is None and args.journey_id is None:
        raise SystemExit("journey_id is required unless --resume is used")
    if args.max_interactions is not None and args.max_interactions < 0:
        raise SystemExit("--max-interactions must be zero or greater")

    base_url = resolve_base_url(args.base_url)
    trace_recorder: JsonlTraceRecorder | None = None
    if args.trace_dir is not None:
        trace_recorder = JsonlTraceRecorder.create(
            args.trace_dir,
            journey_id=args.journey_id,
            consumer="json_cli",
        )

    client = JourneyClient(
        base_url,
        on_exchange=(
            trace_recorder.record_exchange if trace_recorder is not None else None
        ),
    )
    executor = JourneyExecutor(client)
    input_provider = JsonCliInputProvider()

    response_observer: ResponseObserver | None = None
    if args.state_file is not None:
        response_observer = partial(save_response, path=args.state_file)

    if args.resume is not None:
        response = load_response(args.resume)
    else:
        response = executor.start(args.journey_id)
    _observe(response, response_observer)

    response = _drive_cli(
        executor,
        response,
        input_provider,
        max_interactions=args.max_interactions,
        on_response=response_observer,
    )

    if trace_recorder is not None:
        if executor.is_terminal(response):
            trace_recorder.record_finished(response)
        else:
            trace_recorder.record_stopped(
                response,
                reason="maximum_interactions_reached",
            )

    print("\nLatest journey response:")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    if trace_recorder is not None:
        print(f"\nTrace written to {trace_recorder.path}")
    return 0


def _drive_cli(
    executor: JourneyExecutor,
    response: JsonObject,
    input_provider: JsonCliInputProvider,
    *,
    max_interactions: int | None,
    on_response: ResponseObserver | None,
) -> JsonObject:
    """Drive the stepwise executor until completion or the requested limit.

    Args:
        executor: Stepwise journey executor.
        response: Latest complete service response.
        input_provider: CLI interaction collector.
        max_interactions: Optional limit on submitted results.
        on_response: Optional callback for each new service response.

    Returns:
        The latest journey response.
    """
    interactions_processed = 0
    current = dict(response)
    while not executor.is_terminal(current):
        if max_interactions is not None and interactions_processed >= max_interactions:
            return current

        interaction = executor.current_interaction(current)
        if interaction is None:  # pragma: no cover - guarded by is_terminal
            return current
        result = input_provider.collect(interaction)
        current = executor.submit(current, result)
        interactions_processed += 1
        _observe(current, on_response)

    return current


def _observe(
    response: ReadOnlyJsonObject,
    observer: ResponseObserver | None,
) -> None:
    if observer is not None:
        observer(response)


if __name__ == "__main__":
    raise SystemExit(main())
