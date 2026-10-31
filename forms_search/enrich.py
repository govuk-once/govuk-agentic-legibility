"""Generate short descriptions for GOV.UK Forms using Claude on Amazon Bedrock.

Each Form export is rendered to compact text (see ``form_text``) and sent to
Bedrock's Converse API with a prompt asking for a grounded, one-to-two
sentence description. Results are appended to a JSONL cache as they complete,
so an interrupted run can be resumed; the search catalogue is then rebuilt
from the cache.

A cached description is reused when the Form content hash, prompt version and
model all match. Change any of those (or pass ``--force``) to regenerate.

Usage (from the repository root):

    gds-cli aws <profile> -- uv run python -m forms_search.enrich --ids 6 232
    gds-cli aws <profile> -- uv run python -m forms_search.enrich --concurrency 8
    uv run python -m forms_search.enrich --dry-run --ids 6   # print prompt only
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from forms_search.form_text import (
    form_id,
    form_title,
    load_form,
    render_form,
    similar_titles,
    source_hash,
)

logger = logging.getLogger("forms_search.enrich")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FORMS_DIR = REPO_ROOT / "forms_export"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_MODEL_ID = "eu.anthropic.claude-sonnet-5-5"
DEFAULT_REGION = "eu-west-2"

# Bump when SYSTEM_PROMPT or the rendered input changes meaningfully, so
# cached descriptions are regenerated on the next run.
PROMPT_VERSION = "1"
MAX_WORDS = 50
# Allow a little slack over the target before rejecting and retrying.
HARD_MAX_WORDS = 60

SYSTEM_PROMPT = f"""\
You write catalogue descriptions of UK government online forms (GOV.UK Forms). \
The descriptions are indexed by a search tool and read by an AI assistant that \
must choose which form fits a user's request, so they must be accurate and \
specific.

Write one or two sentences, at most {MAX_WORDS} words, saying what the form is \
used for: the task it lets someone complete, and the main information it \
collects when that helps tell it apart.

Rules:
- Use only what the form content shows. Do not invent eligibility rules, \
deadlines, fees, outcomes or capabilities. If something is unclear, leave it out.
- Where similar forms are listed, make clear what this one covers that they do \
not, using details from this form's own content.
- Start with a verb in the imperative, e.g. "Apply for…", "Report…", "Amend…". \
Do not start with "This form" or repeat the title word for word.
- Name the organisation only if the content makes it clear.
- If the title or content marks it as a test or internal form, say so.
- Plain UK English. No marketing language, no markdown, no quotation marks.

Reply with the description text only."""

RETRYABLE_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelNotReadyException",
    "ModelTimeoutException",
}


class ConverseClient(Protocol):
    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Settings:
    model_id: str
    effort: str | None
    max_retries: int
    base_delay: float = 2.0
    max_delay: float = 60.0
    max_tokens: int = 4000


class RetryableError(Exception):
    """A failure worth retrying: throttling, transient service error or bad output."""


@dataclass
class FormJob:
    form_id: str
    title: str
    source_sha256: str
    prompt: str


def build_user_prompt(form: dict[str, Any], similar: list[str]) -> str:
    parts = ["<form>", render_form(form), "</form>"]
    if similar:
        parts.append("\nOther forms in the catalogue with similar titles:")
        parts.extend(f"- {title}" for title in similar)
    parts.append("\nWrite the description.")
    return "\n".join(parts)


def _is_retryable_client_error(exc: Exception) -> bool:
    from botocore.exceptions import (
        ClientError,
        ConnectionClosedError,
        ConnectTimeoutError,
        EndpointConnectionError,
        ReadTimeoutError,
    )

    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code") in RETRYABLE_ERROR_CODES
    return isinstance(
        exc,
        (
            ReadTimeoutError,
            ConnectTimeoutError,
            EndpointConnectionError,
            ConnectionClosedError,
        ),
    )


def _clean_description(text: str) -> str:
    text = " ".join(text.split())
    return text.strip().strip('"“”').strip()


def call_model(
    client: ConverseClient, settings: Settings, prompt: str
) -> tuple[str, dict[str, Any]]:
    """Make one Converse request and return (description, usage)."""
    request: dict[str, Any] = {
        "modelId": settings.model_id,
        "system": [{"text": SYSTEM_PROMPT}],
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": settings.max_tokens},
    }
    if settings.effort:
        request["additionalModelRequestFields"] = {
            "output_config": {"effort": settings.effort}
        }

    try:
        response = client.converse(**request)
    except Exception as exc:
        if _is_retryable_client_error(exc):
            raise RetryableError(str(exc)) from exc
        raise

    stop_reason = response.get("stopReason")
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    text = _clean_description("".join(b["text"] for b in blocks if "text" in b))
    if stop_reason not in ("end_turn", "stop_sequence") or not text:
        raise RetryableError(
            f"unusable response (stopReason={stop_reason!r}, {len(text)} chars)"
        )

    words = len(text.split())
    if words > HARD_MAX_WORDS:
        raise RetryableError(f"description too long ({words} words)")
    return text, response.get("usage", {})


def generate_with_retries(
    client: ConverseClient, settings: Settings, prompt: str, sleep=None
) -> tuple[str, dict[str, Any], int]:
    """Call the model with exponential backoff and full jitter. Returns attempts used too."""
    sleep = sleep or time.sleep
    for attempt in range(settings.max_retries + 1):
        try:
            text, usage = call_model(client, settings, prompt)
            return text, usage, attempt + 1
        except RetryableError as exc:
            if attempt == settings.max_retries:
                raise
            delay = random.uniform(
                0, min(settings.max_delay, settings.base_delay * 2**attempt)
            )
            logger.warning("retrying in %.1fs after: %s", delay, exc)
            sleep(delay)
    raise AssertionError("unreachable")


# --- Cache and catalogue ---------------------------------------------------


def cache_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record["form_id"]),
        record["source_sha256"],
        record["prompt_version"],
        record["model_id"],
    )


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    """Latest cache record per form id. Tolerates a truncated final line."""
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    for line_no, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("skipping unreadable cache line %d in %s", line_no, path)
            continue
        records[str(record["form_id"])] = record
    return records


def is_current(record: dict[str, Any] | None, job: FormJob, model_id: str) -> bool:
    return record is not None and cache_key(record) == (
        job.form_id,
        job.source_sha256,
        PROMPT_VERSION,
        model_id,
    )


def build_catalogue(
    forms: dict[str, dict[str, Any]], cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Catalogue of every Form that has a description for its current content."""
    workflows = []
    missing = []
    for fid in sorted(forms, key=int):
        form = forms[fid]
        record = cache.get(fid)
        if record is None or record["source_sha256"] != source_hash(form):
            missing.append(fid)
            continue
        workflows.append(
            {
                "workflow_id": fid,
                "title": form_title(form),
                "description": record["description"],
                "form_slug": form["content"].get("form_slug"),
                "model_id": record["model_id"],
                "prompt_version": record["prompt_version"],
            }
        )
    return {"workflows": workflows, "missing_descriptions": missing}


def write_json_atomic(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


# --- Runner ----------------------------------------------------------------


def load_forms(forms_dir: Path) -> dict[str, dict[str, Any]]:
    forms = {}
    for path in sorted(forms_dir.glob("*.json")):
        form = load_form(path)
        forms[form_id(form)] = form
    return forms


def build_jobs(forms: dict[str, dict[str, Any]], ids: list[str]) -> list[FormJob]:
    titles = {fid: form_title(f) for fid, f in forms.items()}
    return [
        FormJob(
            form_id=fid,
            title=titles[fid],
            source_sha256=source_hash(forms[fid]),
            prompt=build_user_prompt(forms[fid], similar_titles(fid, titles)),
        )
        for fid in ids
    ]


def run(
    client: ConverseClient,
    settings: Settings,
    jobs: list[FormJob],
    cache_path: Path,
    concurrency: int,
    sleep=None,
) -> tuple[int, list[str]]:
    """Generate descriptions for jobs, appending each result to the cache. Returns (done, failed ids)."""
    lock = threading.Lock()
    failed: list[str] = []
    done = 0

    def work(job: FormJob) -> dict[str, Any]:
        started = time.monotonic()
        text, usage, attempts = generate_with_retries(
            client, settings, job.prompt, sleep=sleep
        )
        return {
            "form_id": job.form_id,
            "title": job.title,
            "description": text,
            "source_sha256": job.source_sha256,
            "prompt_version": PROMPT_VERSION,
            "model_id": settings.model_id,
            "effort": settings.effort,
            "attempts": attempts,
            "usage": {k: usage.get(k) for k in ("inputTokens", "outputTokens")},
            "seconds": round(time.monotonic() - started, 2),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        cache_path.open("a", encoding="utf-8") as cache_file,
        ThreadPoolExecutor(concurrency) as pool,
    ):
        futures = {pool.submit(work, job): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                record = future.result()
            except Exception as exc:
                logger.error("form %s failed: %s", job.form_id, exc)
                failed.append(job.form_id)
                continue
            with lock:
                cache_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                cache_file.flush()
                done += 1
            logger.info(
                "[%d/%d] %s: %s", done, len(jobs), job.form_id, record["description"]
            )
    return done, sorted(failed, key=int)


def make_bedrock_client(region: str, concurrency: int) -> ConverseClient:
    import boto3
    from botocore.config import Config

    # Retries are handled in generate_with_retries so backoff is visible and configurable.
    config = Config(
        retries={"total_max_attempts": 1},
        max_pool_connections=max(10, concurrency),
        read_timeout=300,
    )
    return boto3.client("bedrock-runtime", region_name=region, config=config)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--forms-dir", type=Path, default=DEFAULT_FORMS_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--ids", nargs="+", help="Only these Form ids")
    parser.add_argument("--limit", type=int, help="Only the first N pending Forms")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Parallel Bedrock requests (default 4)",
    )
    parser.add_argument(
        "--max-retries", type=int, default=6, help="Retries per Form (default 6)"
    )
    parser.add_argument(
        "--model-id",
        default=os.environ.get("FORMS_ENRICH_MODEL_ID", DEFAULT_MODEL_ID),
        help=f"Bedrock model or inference profile id (default {DEFAULT_MODEL_ID}, or $FORMS_ENRICH_MODEL_ID)",
    )
    parser.add_argument(
        "--region", default=os.environ.get("AWS_REGION", DEFAULT_REGION)
    )
    parser.add_argument(
        "--effort",
        default="low",
        help="Claude effort level sent as output_config.effort; 'none' to omit (default low)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if a current description is cached",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the prompt for each selected Form and exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args(argv)
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")

    forms = load_forms(args.forms_dir)
    if not forms:
        raise SystemExit(f"no Form exports found in {args.forms_dir}")

    selected = sorted(forms, key=int)
    if args.ids:
        unknown = [i for i in args.ids if i not in forms]
        if unknown:
            raise SystemExit(f"unknown Form ids: {', '.join(unknown)}")
        selected = [i for i in selected if i in set(args.ids)]

    cache_path = args.out_dir / "descriptions.jsonl"
    catalogue_path = args.out_dir / "catalogue.json"
    settings = Settings(
        model_id=args.model_id,
        effort=None if args.effort == "none" else args.effort,
        max_retries=args.max_retries,
    )

    jobs = build_jobs(forms, selected)
    if args.dry_run:
        for job in jobs:
            print(
                f"===== {job.form_id} =====\n[system]\n{SYSTEM_PROMPT}\n\n[user]\n{job.prompt}\n"
            )
        return 0

    cache = load_cache(cache_path)
    pending = [
        j
        for j in jobs
        if args.force or not is_current(cache.get(j.form_id), j, settings.model_id)
    ]
    if args.limit is not None:
        pending = pending[: args.limit]
    logger.info(
        "%d Forms selected, %d already described, %d to generate with %s (concurrency %d)",
        len(jobs),
        len(jobs) - len(pending) if not args.force else 0,
        len(pending),
        settings.model_id,
        args.concurrency,
    )

    failed: list[str] = []
    if pending:
        client = make_bedrock_client(args.region, args.concurrency)
        _, failed = run(client, settings, pending, cache_path, args.concurrency)

    catalogue = build_catalogue(forms, load_cache(cache_path))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(catalogue_path, catalogue)
    logger.info(
        "catalogue: %d described, %d missing -> %s",
        len(catalogue["workflows"]),
        len(catalogue["missing_descriptions"]),
        catalogue_path,
    )
    if failed:
        logger.error(
            "%d Forms failed (re-run to retry): %s", len(failed), " ".join(failed)
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
