"""Compile a single export or batch; unsupported batch members never abort the run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import ORDINARY_SCALARS, UnsupportedForm, compile_form


# For non-repeatable questions this is diagnostic, not an allow-list:
# unfamiliar answer types still compile as preview-only strings.


def _warnings(export: dict, definition: dict) -> list[str]:
    states = definition["processes"]["main"]["states"]
    warnings = []
    for step in export["content"]["steps"]:
        sid = step["id"]
        kind = states[sid]["schema"]["kind"]
        answer_type = step["data"].get("answer_type")
        if answer_type == "address" and kind == "string":
            warnings.append(f"{sid}: address collected as one string; original address configuration retained")
        elif answer_type == "file":
            warnings.append(f"{sid}: file_ref needs an upload-capable client; adapter does not store file bytes")
        elif answer_type not in ORDINARY_SCALARS | {"selection", "file"}:
            warnings.append(f"{sid}: unrecognised answer_type {answer_type!r} compiled as a string (preview only)")
    if export["content"].get("payment_url"):
        warnings.append("payment is simulated only: preview-only; no real payment or submission")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile GOV.UK Forms to SFSM/0.2")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="one exported Forms JSON file")
    source.add_argument("--batch", type=Path, help="directory containing exported Forms JSON")
    parser.add_argument("--output", type=Path, required=True, help="output JSON (single) or directory (batch)")
    parser.add_argument("--report", type=Path, help="write machine-readable batch report")
    args = parser.parse_args()
    paths = sorted(args.batch.glob("*.json")) if args.batch else [args.input]
    if not paths:
        parser.error("no JSON exports found")
    if args.batch:
        if args.batch.resolve() == args.output.resolve():
            parser.error("batch output must differ from original export directory")
        args.output.mkdir(parents=True, exist_ok=True)
    elif args.output.is_dir():
        parser.error("single-form --output must be a file")
    elif args.input.resolve() == args.output.resolve():
        parser.error("output must differ from original export")
    results: list[dict[str, object]] = []
    for path in paths:
        dest = args.output / path.name if args.batch else args.output
        # Rejecting a previously accepted form must also remove stale compiled
        # JSON or the filesystem workflow server could continue serving it.
        dest.unlink(missing_ok=True)
        try:
            export = json.loads(path.read_text(encoding="utf-8"))
            definition = compile_form(export)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(definition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            #print(f"OK          {path.name} -> {dest}")
            warnings = _warnings(export, definition)
            partial = bool(export["content"].get("payment_url")) or any(
                "unrecognised answer_type" in w for w in warnings)
            result = {"file": path.name, "status": "preview_only" if partial else "ok", "output": str(dest)}
            if warnings:
                result["warnings"] = warnings
            results.append(result)
        except (UnsupportedForm, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            print(f"UNSUPPORTED {path.name}: {error}")
            results.append({"file": path.name, "status": "unsupported", "reason": str(error)})
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(item["status"] == "ok" for item in results)
    preview = sum(item["status"] == "preview_only" for item in results)
    print(f"Compiled {passed}/{len(results)}; preview-only {preview}; unsupported {len(results) - passed - preview}")
    return 0 if args.batch or passed + preview == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
