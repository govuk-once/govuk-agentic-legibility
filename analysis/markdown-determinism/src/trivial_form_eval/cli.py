import argparse
import json
import os
import sys
from pathlib import Path

from litellm import _turn_on_debug

from trivial_form_eval.analysis import analyse_run_dir
from trivial_form_eval.fixture import load_fixture
from trivial_form_eval.io import write_json
from trivial_form_eval.model import litellm_completion
from trivial_form_eval.request import build_request, resolve_model
from trivial_form_eval.runner import run_experiment

INTERRUPT_EXIT_CODE = 130
EXPERIMENT_CONFIG_FILENAME = "experiment.json"

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parsed_argv = argv if argv is not None else sys.argv[1:]
    args = parser.parse_args(parsed_argv)

    if args.command in {"dry-run", "run"}:
        apply_fixture_config(args, parsed_argv, parser)

        if args.debug:
            _turn_on_debug()

    if args.command == "dry-run":
        return dry_run(args)

    if args.command == "run":
        return run_command(args)

    if args.command == "analyse":
        return analyse_command(args)

    parser.print_help()
    return 2


def apply_fixture_config(
    args: argparse.Namespace,
    argv: list[str],
    parser: argparse.ArgumentParser,
) -> None:
    config_path = args.fixture / EXPERIMENT_CONFIG_FILENAME

    if not config_path.is_file():
        parser.error(
            f"Fixture configuration does not exist: {config_path}"
        )

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        parser.error(
            f"Fixture configuration is not valid JSON: "
            f"{config_path}: {exc}"
        )

    if not isinstance(config_data, dict):
        parser.error(
            f"Fixture configuration must contain a JSON object: "
            f"{config_path}"
        )

    if "fixture" in config_data:
        parser.error(
            f"{config_path} must not contain a 'fixture' setting. "
            "The fixture is determined by the directory passed to the command."
        )

    known_settings = {
        "model",
        "runs",
        "concurrency",
        "output_dir",
        "max_retries",
        "stop_after",
        "finalise_on_interrupt",
        "progress",
        "no_fail",
        "debug",
    }

    explicit_settings = explicit_cli_settings(argv)

    for key, value in config_data.items():
        attr_name = key.replace("-", "_")

        if attr_name not in known_settings:
            parser.error(
                f"Unknown setting {key!r} in {config_path}"
            )

        # Some run settings are irrelevant to dry-run. Ignore them rather
        # than rejecting a configuration shared by both commands.
        if not hasattr(args, attr_name):
            continue

        # Explicit command-line arguments take precedence over the fixture
        # configuration.
        if attr_name in explicit_settings:
            continue

        if attr_name == "output_dir":
            value = Path(value)

        setattr(args, attr_name, value)


def explicit_cli_settings(argv: list[str]) -> set[str]:
    settings: set[str] = set()

    boolean_aliases = {
        "--progress": "progress",
        "--no-progress": "progress",
        "--finalise-on-interrupt": "finalise_on_interrupt",
        "--no-finalise-on-interrupt": "finalise_on_interrupt",
    }

    for argument in argv:
        if not argument.startswith("--"):
            continue

        flag = argument.split("=", maxsplit=1)[0]

        if flag in boolean_aliases:
            settings.add(boolean_aliases[flag])
        else:
            settings.add(flag[2:].replace("-", "_"))

    return settings

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trivial-form-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry = subparsers.add_parser(
        "dry-run",
        help="Render the request without making a model call.",
    )
    dry.add_argument(
        "fixture",
        type=Path,
        help=(
            "Fixture directory. Experiment settings are loaded from "
            "<fixture>/experiment.json."
        ),
    )
    dry.add_argument("--model")
    dry.add_argument("--debug", action="store_true")

    run = subparsers.add_parser(
        "run",
        help="Run a live experiment.",
    )
    run.add_argument(
        "fixture",
        type=Path,
        help=(
            "Fixture directory. Experiment settings are loaded from "
            "<fixture>/experiment.json."
        ),
    )
    run.add_argument("--runs", type=int, default=10)
    run.add_argument("--model")
    run.add_argument("--concurrency", type=int, default=1)
    run.add_argument("--output-dir", type=Path, default=Path("runs"))
    run.add_argument("--max-retries", type=int, default=2)
    run.add_argument(
        "--stop-after",
        type=int,
        help=(
            "Stop after this many completed calls, then still write "
            "analysis files."
        ),
    )
    run.add_argument(
        "--finalise-on-interrupt",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "On Ctrl+C, stop making calls and still write available "
            "analysis files."
        ),
    )
    run.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show a terminal progress bar while calls complete.",
    )
    run.add_argument("--no-fail", action="store_true")
    run.add_argument("--debug", action="store_true")

    analyse = subparsers.add_parser(
        "analyse",
        help="Analyse a saved experiment.",
    )
    analyse.add_argument("run_dir", type=Path)

    return parser


def dry_run(args: argparse.Namespace) -> int:
    fixture = load_fixture(args.fixture)
    request = build_request(fixture, resolve_model(args.model))
    rendered = {
        "requested_model": request.model,
        "messages": request.messages,
        "tool_definition": request.tools,
        "tool_choice": request.tool_choice,
        "additional_model_parameters": request.model_parameters,
        "expected_arguments_not_sent_to_model": fixture.expected_arguments,
        "note": (
            "Expected arguments are shown separately for inspection and are not sent to the model."
        ),
    }
    print(json.dumps(rendered, indent=2, sort_keys=True, ensure_ascii=False))
    print("\nNo model call was made.")
    return 0


def run_command(args: argparse.Namespace) -> int:
    if args.runs < 1:
        print("--runs must be at least 1", file=sys.stderr)
        return 2
    if args.concurrency < 1:
        print("--concurrency must be at least 1", file=sys.stderr)
        return 2
    if args.stop_after is not None and args.stop_after < 1:
        print("--stop-after must be at least 1", file=sys.stderr)
        return 2
    run_dir = run_experiment(
        fixture_path=args.fixture,
        runs=args.runs,
        model=args.model,
        concurrency=args.concurrency,
        output_dir=args.output_dir,
        max_retries=args.max_retries,
        completion_func=litellm_completion,
        stop_after=args.stop_after,
        finalise_on_interrupt=args.finalise_on_interrupt,
        progress=args.progress,
    )
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    print_report(run_dir, summary)
    if manifest.get("stop_reason") == "keyboard_interrupt":
        exit_code = 0 if args.no_fail else INTERRUPT_EXIT_CODE
        print(f"Run finalised after Ctrl+C. Exiting with code {exit_code}.")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
    return 0 if args.no_fail or summary["every_requested_run_correct"] else 1


def analyse_command(args: argparse.Namespace) -> int:
    summary, variants, differences = analyse_run_dir(args.run_dir)
    write_json(args.run_dir / "summary.json", summary)
    write_json(args.run_dir / "variants.json", variants)
    (args.run_dir / "differences.txt").write_text(differences, encoding="utf-8")
    print_report(args.run_dir, summary)
    return 0 if summary["every_requested_run_correct"] else 1


def print_report(run_dir: Path, summary: dict[str, object]) -> None:
    print(f"Run directory: {run_dir}")
    print(f"Requested runs: {summary['requested_runs']}")
    print(f"Completed runs: {summary['completed_runs']} ({summary['completion_rate']:.2%})")
    print("Outcome rates use completed runs as the denominator.")
    print(f"Correct: {summary['correct_count']} ({summary['correct_rate']:.2%})")
    print(
        "Exact expected matches: "
        f"{summary['exact_expected_match_count']} "
        f"({summary['exact_expected_match_rate']:.2%})"
    )
    print(
        "Accepted expected matches: "
        f"{summary['accepted_expected_match_count']} "
        f"({summary['accepted_expected_match_rate']:.2%})"
    )
    print(f"Schema valid: {summary['schema_valid_count']} ({summary['schema_valid_rate']:.2%})")
    print(
        "Exactly one correct tool call: "
        f"{summary['exactly_one_correct_tool_call_count']} "
        f"({summary['exactly_one_correct_tool_call_rate']:.2%})"
    )
    print(f"Unique raw argument strings: {summary['unique_raw_tool_argument_strings']}")
    print(
        "Unique canonical valid argument objects: "
        f"{summary['unique_canonical_valid_argument_objects']}"
    )
    mismatches = summary.get("field_level_mismatch_counts")
    if isinstance(mismatches, dict) and mismatches:
        print("Field mismatches:")
        for path, count in sorted(mismatches.items()):
            print(f"  {path}: {count}")
        print(f"Readable differences: {run_dir / 'differences.txt'}")
    print(f"Every requested run correct: {summary['every_requested_run_correct']}")
