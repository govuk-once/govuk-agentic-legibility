"""Command-line interface for the generic server-driven journey executor."""

from __future__ import annotations

import argparse
import json
from functools import partial
from pathlib import Path
from typing import Sequence

from agents.src.workflow_executor.client import JourneyClient
from agents.src.workflow_executor.config import (
    load_executor_environment,
    resolve_base_url,
)
from agents.src.workflow_executor.executor import JourneyExecutor, ResponseObserver
from agents.src.workflow_executor.input_provider import JsonCliInputProvider
from agents.src.workflow_executor.state import load_response, save_response


def build_parser() -> argparse.ArgumentParser:
    """Create the workflow-executor argument parser."""
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

    base_url = resolve_base_url(args.base_url)
    executor = JourneyExecutor(JourneyClient(base_url))
    input_provider = JsonCliInputProvider()

    response_observer: ResponseObserver | None = None # ruff needs this specified
    if args.state_file is not None:
        response_observer = partial(save_response, path=args.state_file)

    if args.resume is not None:
        response = executor.continue_from(
            load_response(args.resume),
            input_provider,
            max_interactions=args.max_interactions,
            on_response=response_observer,
        )
    else:
        response = executor.run(
            args.journey_id,
            input_provider,
            max_interactions=args.max_interactions,
            on_response=response_observer,
        )

    print("\nLatest journey response:")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
