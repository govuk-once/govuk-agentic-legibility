"""Structural/DI validation. XSD and bpmn-js import are independent extra checks."""

import json
import math
from xml.etree import ElementTree as ET

from .converter import NS


def validate_bpmn(xml: str, questions: dict | None = None) -> dict:
    root = ET.fromstring(xml)
    ids = [item.attrib["id"] for item in root.iter() if "id" in item.attrib]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate BPMN/DI IDs")
    by_id = {item.attrib["id"]: item for item in root.iter() if "id" in item.attrib}
    parent = {child: item for item in root.iter() for child in item}
    process = root.find("bpmn:process", NS)
    if process is None or process.get("isExecutable") != "false":
        raise ValueError("expected non-executable visual process")
    node_tags = {
        f"{{{NS['bpmn']}}}" + t
        for t in (
            "startEvent",
            "endEvent",
            "userTask",
            "task",
            "scriptTask",
            "exclusiveGateway",
            "subProcess",
        )
    }
    flow_nodes = {i for i, e in by_id.items() if e.tag in node_tags}
    flow_ids = set()
    for scope in [process, *root.findall(".//bpmn:subProcess", NS)]:
        local = {c.get("id"): c for c in scope if c.tag in node_tags}
        starts = [i for i, n in local.items() if n.tag.endswith("startEvent")]
        if len(starts) != 1:
            raise ValueError("each BPMN scope must have one start event")
        local_flows = scope.findall("bpmn:sequenceFlow", NS)
        incoming = {i: [] for i in local}
        outgoing = {i: [] for i in local}
        for flow in local_flows:
            fid, a, b = flow.get("id"), flow.get("sourceRef"), flow.get("targetRef")
            flow_ids.add(fid)
            if a not in local or b not in local:
                raise ValueError("sequence flow crosses scope or has missing endpoint")
            incoming[b].append(fid)
            outgoing[a].append(fid)
            expr = flow.find("bpmn:conditionExpression", NS)
            if expr is not None:
                json.loads(expr.text)
        seen, queue = set(), starts[:]
        adjacency = {i: [by_id[f].get("targetRef") for f in outgoing[i]] for i in local}
        while queue:
            i = queue.pop()
            if i in seen:
                continue
            seen.add(i)
            queue.extend(adjacency[i])
        if seen != local.keys():
            raise ValueError("unreachable node in BPMN scope")
        for nid, n in local.items():
            if sorted(i.text for i in n.findall("bpmn:incoming", NS)) != sorted(
                incoming[nid]
            ) or sorted(i.text for i in n.findall("bpmn:outgoing", NS)) != sorted(
                outgoing[nid]
            ):
                raise ValueError(
                    "incoming/outgoing references disagree with sequence flows"
                )
            if n.tag.endswith("startEvent") and incoming[nid]:
                raise ValueError("start event has incoming flow")
            if n.tag.endswith("endEvent") and outgoing[nid]:
                raise ValueError("end event has outgoing flow")
            if not n.tag.endswith("endEvent") and not outgoing[nid]:
                raise ValueError("non-terminal node has no outgoing flow")
            default = n.get("default")
            if n.tag.endswith("exclusiveGateway") and len(outgoing[nid]) > 1:
                if (
                    default not in outgoing[nid]
                    or by_id[default].find("bpmn:conditionExpression", NS) is not None
                ):
                    raise ValueError("gateway needs a valid unconditional default")
                if any(
                    by_id[f].find("bpmn:conditionExpression", NS) is None
                    for f in outgoing[nid]
                    if f != default
                ):
                    raise ValueError("non-default gateway flow has no condition")
            if questions is not None and n.tag.endswith("userTask"):
                ref = n.find("bpmn:extensionElements/forms:questionRef", NS)
                if (
                    ref is None
                    or ref.get("href").split("#/questions/")[-1]
                    not in questions["questions"]
                ):
                    raise ValueError("missing sidecar question reference")
    shapes = root.findall(".//bpmndi:BPMNShape", NS)
    diagram_edges = root.findall(".//bpmndi:BPMNEdge", NS)
    shape_map = {s.get("bpmnElement"): s for s in shapes}
    if len(shape_map) != len(shapes) or shape_map.keys() != flow_nodes:
        raise ValueError("DI shapes must cover all and only flow nodes")
    if (
        len(diagram_edges) != len(flow_ids)
        or {e.get("bpmnElement") for e in diagram_edges} != flow_ids
    ):
        raise ValueError("DI edges must cover every sequence flow once")
    boxes = {}
    for nid, s in shape_map.items():
        bounds = s.find("dc:Bounds", NS)
        if bounds is None:
            raise ValueError("shape has no bounds")
        box = tuple(float(bounds.get(k)) for k in ("x", "y", "width", "height"))
        if not all(math.isfinite(v) for v in box) or min(box) < 0 or min(box[2:]) <= 0:
            raise ValueError("invalid diagram bounds")
        boxes[nid] = box
    for nid, (x, y, w, h) in boxes.items():
        owner = parent[by_id[nid]]
        if owner.tag.endswith("subProcess"):
            px, py, pw, ph = boxes[owner.get("id")]
            if not (px <= x and py <= y and x + w <= px + pw and y + h <= py + ph):
                raise ValueError("child diagram escapes subprocess bounds")
    for edge in diagram_edges:
        points = [
            (float(p.get("x")), float(p.get("y")))
            for p in edge.findall("di:waypoint", NS)
        ]
        if len(points) < 2 or not all(
            math.isfinite(v) and v >= 0 for pt in points for v in pt
        ):
            raise ValueError("invalid edge waypoints")
        flow = by_id[edge.get("bpmnElement")]
        for nid, pt in [
            (flow.get("sourceRef"), points[0]),
            (flow.get("targetRef"), points[-1]),
        ]:
            x, y, w, h = boxes[nid]
            a, b = pt
            if not (
                x - 0.01 <= a <= x + w + 0.01
                and y - 0.01 <= b <= y + h + 0.01
                and min(abs(a - x), abs(a - x - w), abs(b - y), abs(b - y - h)) < 0.01
            ):
                raise ValueError("edge endpoint does not dock to its shape")
    return {
        "nodes": len(flow_nodes),
        "flows": len(flow_ids),
        "shapes": len(shapes),
        "edges": len(diagram_edges),
    }
