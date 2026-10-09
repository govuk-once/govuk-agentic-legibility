"""Replace only the diagram interchange in a generated Forms BPMN file.

Usage: python -m forms_bpmn.relayout --input form.bpmn --output form.bpmn
Question sidecars are not needed. Stable process/flow IDs and metadata stay intact.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .converter import NS, Edge, Graph, Node, el, layout, write_di
from .validate import validate_bpmn

SUPPORTED = {"startEvent", "endEvent", "exclusiveGateway", "userTask", "task", "scriptTask", "subProcess"}


def scope_graph(scope):
    nodes, edges = {}, []
    for item in scope:
        tag = item.tag.removeprefix("{" + NS["bpmn"] + "}")
        if tag in SUPPORTED:
            nid = item.get("id")
            if not nid or nid in nodes:
                raise ValueError("Missing or duplicate node ID")
            child = scope_graph(item) if tag == "subProcess" else None
            nodes[nid] = Node(nid, tag, item.get("name", ""), children=child)
        elif tag == "sequenceFlow":
            edges.append(Edge(item.get("id"), item.get("sourceRef"), item.get("targetRef"), item.get("name", "")))
        elif tag not in {"extensionElements", "documentation", "incoming", "outgoing"}:
            raise ValueError(f"Relayout does not support {tag}")
    starts = [n.id for n in nodes.values() if n.kind == "startEvent"]
    if len(starts) != 1:
        raise ValueError("Expected one start event per scope")
    for edge in edges:
        if not edge.id or edge.source not in nodes or edge.target not in nodes:
            raise ValueError("Invalid flow ID or endpoint")
        owner = next(item for item in scope if item.get("id") == edge.source)
        edge.default = owner.get("default") == edge.id
    return Graph(nodes, edges, starts[0])


def relayout_bpmn(xml: str) -> str:
    root = ET.fromstring(xml)
    processes = root.findall("bpmn:process", NS)
    if len(processes) != 1 or root.find("bpmn:collaboration", NS) is not None:
        raise ValueError("Relayout supports one generated Forms process, without collaboration")
    # Constrain the tool to the converter's output, rather than guessing layouts
    # for arbitrary executable BPMN or losing unsupported diagram elements.
    if not root.findall(".//forms:stateRef", NS):
        raise ValueError("Expected Forms converter extension metadata")
    validate_bpmn(xml)
    process = processes[0]
    graph = scope_graph(process)
    layout(graph)
    for old in root.findall("bpmndi:BPMNDiagram", NS):
        root.remove(old)
    diagram = el(root, "bpmndi:BPMNDiagram", id="diagram_" + process.get("id"))
    plane = el(diagram, "bpmndi:BPMNPlane", id="plane_" + process.get("id"), bpmnElement=process.get("id"))
    write_di(plane, graph)
    ET.indent(root, space="  ")
    result = ET.tostring(root, encoding="unicode", xml_declaration=True)
    validate_bpmn(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = relayout_bpmn(args.input.read_text(encoding="utf-8"))
    except (ValueError, ET.ParseError) as error:
        parser.exit(1, f"Cannot relayout: {error}\n")
    # Parse and calculate before any write; identical input/output is supported.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(result + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if args.output.exists():
            temporary.chmod(args.output.stat().st_mode & 0o777)
        temporary.replace(args.output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(args.output)


if __name__ == "__main__":
    main()
