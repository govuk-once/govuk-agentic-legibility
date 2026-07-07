import json
from pathlib import Path

from trivial_form_eval.cli import (
    apply_fixture_config,
    build_parser,
)


def write_config(fixture_path: Path, config: dict[str, object]) -> None:
    fixture_path.mkdir()
    (fixture_path / "experiment.json").write_text(
        json.dumps(config),
        encoding="utf-8",
    )


def test_loads_experiment_settings_from_fixture_directory(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "example_fixture"
    write_config(
        fixture_path,
        {
            "model": "bedrock/test-model",
            "runs": 100,
            "concurrency": 5,
            "max_retries": 7,
        },
    )

    argv = ["run", str(fixture_path)]
    parser = build_parser()
    args = parser.parse_args(argv)

    apply_fixture_config(args, argv, parser)

    assert args.fixture == fixture_path
    assert args.model == "bedrock/test-model"
    assert args.runs == 100
    assert args.concurrency == 5
    assert args.max_retries == 7


def test_command_line_arguments_override_fixture_settings(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "example_fixture"
    write_config(
        fixture_path,
        {
            "runs": 100,
            "concurrency": 5,
            "progress": True,
        },
    )

    argv = [
        "run",
        str(fixture_path),
        "--runs",
        "1",
        "--no-progress",
    ]
    parser = build_parser()
    args = parser.parse_args(argv)

    apply_fixture_config(args, argv, parser)

    assert args.runs == 1
    assert args.concurrency == 5
    assert args.progress is False


def test_dry_run_uses_model_from_fixture_configuration(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "example_fixture"
    write_config(
        fixture_path,
        {
            "model": "bedrock/test-model",
            "runs": 100,
            "concurrency": 5,
        },
    )

    argv = ["dry-run", str(fixture_path)]
    parser = build_parser()
    args = parser.parse_args(argv)

    apply_fixture_config(args, argv, parser)

    assert args.fixture == fixture_path
    assert args.model == "bedrock/test-model"