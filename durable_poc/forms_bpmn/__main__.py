"""Convert one export to BPMN, a linked metadata sidecar and an SVG preview."""

import argparse
import json
from pathlib import Path

from forms_adapter import UnsupportedForm

from .converter import convert_form
from .render import render_svg
from .validate import validate_bpmn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="destination .bpmn file"
    )
    parser.add_argument("--mode", choices=["flat", "auto"], default="flat")
    args = parser.parse_args()
    output = args.output
    if output.suffix != ".bpmn":
        parser.error("output must end in .bpmn")
    paths = [
        output,
        output.with_suffix(".questions.json"),
        output.with_suffix(".svg"),
        output.with_suffix(".report.json"),
    ]
    if args.input.resolve() in {p.resolve() for p in paths}:
        parser.error("output must not overwrite source")
    try:
        export = json.loads(args.input.read_text(encoding="utf-8"))
        result = convert_form(export, mode=args.mode, question_file=paths[1].name)
        validate_bpmn(result.xml, result.questions)
    except (UnsupportedForm, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"UNSUPPORTED: {exc}\n")
    # Validate everything before creating any output. An old result is retained
    # on a failed conversion; exit status is the authority, never a stale file.
    output.parent.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(result.xml + "\n", encoding="utf-8")
    paths[1].write_text(
        json.dumps(result.questions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths[2].write_text(
        render_svg(result.graph, export["content"]["name"].strip()), encoding="utf-8"
    )
    paths[3].write_text(
        json.dumps(result.report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"{output}: {result.report['question_count']} questions; {len(result.report['decomposition'])} expanded subprocesses"
    )
    for warning in result.report["warnings"]:
        print("NOTE: " + warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
