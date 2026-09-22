"""Compile a single export or batch; unsupported batch members never abort the run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import UnsupportedForm, compile_form


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
        args.output.mkdir(parents=True, exist_ok=True)
    elif args.output.is_dir():
        parser.error("single-form --output must be a file")
    results: list[dict[str, str]] = []
    for path in paths:
        try:
            definition = compile_form(json.loads(path.read_text(encoding="utf-8")))
            dest = args.output / path.name if args.batch else args.output
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(definition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"OK          {path.name} -> {dest}")
            results.append({"file": path.name, "status": "ok", "output": str(dest)})
        except (UnsupportedForm, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            print(f"UNSUPPORTED {path.name}: {error}")
            results.append({"file": path.name, "status": "unsupported", "reason": str(error)})
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(item["status"] == "ok" for item in results)
    print(f"Compiled {passed}/{len(results)}; unsupported {len(results) - passed}")
    return 0 if args.batch or passed == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
