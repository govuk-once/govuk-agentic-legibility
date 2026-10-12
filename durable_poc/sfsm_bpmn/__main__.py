"""Export SFSM to one BPMN file with linked processes and local JSON metadata."""

import argparse
import json
from pathlib import Path

from .converter import convert_sfsm
from .validate import validate_bpmn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="destination .bpmn file"
    )
    args = parser.parse_args()
    if args.output.suffix != ".bpmn":
        parser.error("output must end in .bpmn")
    paths = [
        args.output,
        args.output.with_suffix(".questions.json"),
        args.output.with_suffix(".report.json"),
    ]
    if args.input.resolve() in {p.resolve() for p in paths}:
        parser.error("output must not overwrite source")
    try:
        source = json.loads(args.input.read_text(encoding="utf-8"))
        result = convert_sfsm(source, question_file=paths[1].name)
        validate_bpmn(result.xml, result.questions)
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"UNSUPPORTED: {exc}\n")
    # All conversion and validation finish before touching existing outputs.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(result.xml + "\n", encoding="utf-8")
    paths[1].write_text(
        json.dumps(result.questions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths[2].write_text(
        json.dumps(result.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{args.output}: {len(result.graphs)} linked processes, {len(result.questions['questions'])} questions"
    )
    for warning in result.report["warnings"]:
        print("NOTE: " + warning)


if __name__ == "__main__":
    main()
