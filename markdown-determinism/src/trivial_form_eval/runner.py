import copy
import platform
import shutil
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import __version__ as pydantic_version

from trivial_form_eval import __version__
from trivial_form_eval.analysis import analyse_run_dir
from trivial_form_eval.evaluation import (
    EvaluationContext,
    evaluate_api_failure,
    evaluate_response,
    is_transient_exception,
    utc_now_iso,
)
from trivial_form_eval.fixture import Fixture, load_fixture
from trivial_form_eval.io import JsonlWriter, write_json
from trivial_form_eval.request import RequestConfig, build_request, resolve_model

CompletionFunc = Callable[..., Any]


def run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]


def run_experiment(
    *,
    fixture_path: Path,
    runs: int,
    model: str | None,
    concurrency: int,
    output_dir: Path,
    max_retries: int,
    completion_func: CompletionFunc,
    stop_after: int | None = None,
    finalise_on_interrupt: bool = True,
    progress: bool = False,
) -> Path:
    fixture = load_fixture(fixture_path)
    request_config = build_request(fixture, resolve_model(model))
    request_snapshot = copy.deepcopy(request_config.as_litellm_kwargs())
    context = EvaluationContext.from_fixture(fixture)

    current_run_id = run_id()
    run_dir = output_dir / current_run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    start_time = utc_now_iso()
    manifest = build_manifest(
        fixture=fixture,
        run_id_value=current_run_id,
        requested_runs=runs,
        request_config=request_config,
        concurrency=concurrency,
        max_retries=max_retries,
        start_time=start_time,
    )
    write_json(run_dir / "manifest.json", manifest)
    write_json(run_dir / "request.json", request_config.as_saved_json())
    write_json(run_dir / "expected_arguments.json", fixture.expected_arguments)
    write_json(run_dir / "evaluation.json", fixture.evaluation_config)

    records: list[dict[str, Any]] = []
    stop_reason = "completed"
    requested_call_count = min(runs, stop_after) if stop_after else runs
    progress_bar = ProgressBar(total=runs, enabled=progress)

    try:
        with JsonlWriter(run_dir / "responses.jsonl") as writer:
            if concurrency <= 1:
                for number in range(1, requested_call_count + 1):
                    try:
                        record = execute_one(
                            run_number=number,
                            request_snapshot=request_snapshot,
                            requested_model=request_config.model,
                            max_retries=max_retries,
                            completion_func=completion_func,
                            context=context,
                        )
                    except KeyboardInterrupt:
                        stop_reason = "keyboard_interrupt"
                        if not finalise_on_interrupt:
                            raise
                        break
                    writer.write(record)
                    records.append(record)
                    progress_bar.update(len(records))
            else:
                executor = ThreadPoolExecutor(max_workers=concurrency)
                futures = [
                    executor.submit(
                        execute_one,
                        run_number=number,
                        request_snapshot=request_snapshot,
                        requested_model=request_config.model,
                        max_retries=max_retries,
                        completion_func=completion_func,
                        context=context,
                    )
                    for number in range(1, requested_call_count + 1)
                ]
                try:
                    for future in as_completed(futures):
                        record = future.result()
                        writer.write(record)
                        records.append(record)
                        progress_bar.update(len(records))
                except KeyboardInterrupt:
                    stop_reason = "keyboard_interrupt"
                    executor.shutdown(wait=False, cancel_futures=True)
                    if not finalise_on_interrupt:
                        raise
                else:
                    executor.shutdown()

            if stop_after and len(records) >= stop_after and stop_after < runs:
                stop_reason = "stop_after"
    finally:
        progress_bar.finish()

    summary, variants, differences = analyse_run_dir(run_dir)
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "variants.json", variants)
    (run_dir / "differences.txt").write_text(differences, encoding="utf-8")

    manifest["finished_at_utc"] = utc_now_iso()
    manifest["stop_reason"] = stop_reason
    manifest["completed_runs"] = len(records)
    returned_models = sorted(
        {
            record["returned_model"]
            for record in records
            if isinstance(record.get("returned_model"), str)
        }
    )
    providers = sorted(
        {record["provider"] for record in records if isinstance(record.get("provider"), str)}
    )
    manifest["returned_model_identifiers"] = returned_models
    manifest["providers"] = providers
    write_json(run_dir / "manifest.json", manifest)
    return run_dir


def execute_one(
    *,
    run_number: int,
    request_snapshot: dict[str, Any],
    requested_model: str,
    max_retries: int,
    completion_func: CompletionFunc,
    context: EvaluationContext,
) -> dict[str, Any]:
    start = time.perf_counter()
    start_time = utc_now_iso()
    attempts = 0

    while True:
        attempts += 1
        try:
            response = completion_func(**copy.deepcopy(request_snapshot))
            finish_time = utc_now_iso()
            return evaluate_response(
                run_number=run_number,
                requested_model=requested_model,
                start_time=start_time,
                finish_time=finish_time,
                latency_seconds=time.perf_counter() - start,
                attempts=attempts,
                response=response,
                context=context,
            )
        except Exception as exc:
            if attempts <= max_retries and is_transient_exception(exc):
                sleep_time = (2**attempts) * 0.5
                time.sleep(sleep_time)
                continue
            finish_time = utc_now_iso()
            return evaluate_api_failure(
                run_number=run_number,
                requested_model=requested_model,
                start_time=start_time,
                finish_time=finish_time,
                latency_seconds=time.perf_counter() - start,
                attempts=attempts,
                exc=exc,
            )


def build_manifest(
    *,
    fixture: Fixture,
    run_id_value: str,
    requested_runs: int,
    request_config: RequestConfig,
    concurrency: int,
    max_retries: int,
    start_time: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id_value,
        "started_at_utc": start_time,
        "finished_at_utc": None,
        "stop_reason": None,
        "completed_runs": 0,
        "fixture_path": str(fixture.path),
        "expected_tool_name": fixture.expected_tool_name,
        "requested_runs": requested_runs,
        "requested_model": request_config.model,
        "returned_model_identifiers": [],
        "providers": [],
        "concurrency": concurrency,
        "retry_configuration": {"max_retries": max_retries},
        "package_version": __version__,
        "litellm_version": package_version("litellm"),
        "jsonschema_version": package_version("jsonschema"),
        "python_version": platform.python_version(),
        "pydantic_version": pydantic_version,
        "model_parameters": request_config.model_parameters,
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
    }


def package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


class ProgressBar:
    def __init__(self, *, total: int, enabled: bool) -> None:
        self.total = total
        self.enabled = enabled
        self.last_completed = 0
        self._finished = False

    def update(self, completed: int) -> None:
        self.last_completed = completed
        if not self.enabled:
            return
        width = min(40, max(20, shutil.get_terminal_size((80, 20)).columns - 45))
        filled = round(width * completed / self.total) if self.total else width
        bar = "#" * filled + "-" * (width - filled)
        percent = completed / self.total if self.total else 1
        sys.stderr.write(f"\r[{bar}] {completed}/{self.total} {percent:.1%}")
        sys.stderr.flush()

    def finish(self) -> None:
        if self.enabled and not self._finished:
            sys.stderr.write("\n")
            sys.stderr.flush()
            self._finished = True
