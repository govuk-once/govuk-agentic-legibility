"""Structural and coordinate checks for multi-process visual BPMN."""

import json
import math
from xml.etree import ElementTree as ET

from forms_bpmn.converter import NS

NODE_TYPES = {
    "startEvent",
    "endEvent",
    "userTask",
    "exclusiveGateway",
    "task",
    "scriptTask",
    "callActivity",
    "serviceTask",
    "boundaryEvent",
}


def validate_bpmn(xml, questions=None):
    root = ET.fromstring(xml)
    ids = [n.get("id") for n in root.iter() if n.get("id")]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate IDs")
    processes = root.findall("bpmn:process", NS)
    if not processes:
        raise ValueError("no processes")
    nodes = {}
    flows = {}
    scopes = {}
    for process in processes:
        if process.get("isExecutable") != "false":
            raise ValueError("expected non-executable process")
        pid = process.get("id")
        local = {n.get("id"): n for n in process if n.tag.split("}")[-1] in NODE_TYPES}
        start = [i for i, n in local.items() if n.tag.endswith("startEvent")]
        if len(start) != 1:
            raise ValueError("process must have one start event")
        nodes.update(local)
        scopes.update({i: pid for i in local})
        incoming = {i: [] for i in local}
        outgoing = {i: [] for i in local}
        for f in process.findall("bpmn:sequenceFlow", NS):
            a, b = f.get("sourceRef"), f.get("targetRef")
            if a not in local or b not in local:
                raise ValueError("cross-process or missing flow endpoint")
            flows[f.get("id")] = f
            incoming[b].append(f.get("id"))
            outgoing[a].append(f.get("id"))
            expr = f.find("bpmn:conditionExpression", NS)
            if expr is not None:
                json.loads(expr.text)
        for i, n in local.items():
            kind = n.tag.split("}")[-1]
            if sorted(e.text for e in n.findall("bpmn:incoming", NS)) != sorted(
                incoming[i]
            ) or sorted(e.text for e in n.findall("bpmn:outgoing", NS)) != sorted(
                outgoing[i]
            ):
                raise ValueError("flow references disagree")
            if kind == "callActivity" and n.get("calledElement") not in {
                p.get("id") for p in processes
            }:
                raise ValueError("unresolved calledElement")
            if kind == "boundaryEvent":
                target = local.get(n.get("attachedToRef"))
                if (
                    target is None
                    or not target.tag.endswith("serviceTask")
                    or incoming[i]
                ):
                    raise ValueError("invalid error boundary attachment")
                if (
                    n.find("bpmn:errorEventDefinition", NS) is None
                    or n.get("cancelActivity") != "true"
                ):
                    raise ValueError("expected interrupting error event")
            if kind == "endEvent" and outgoing[i]:
                raise ValueError("end has outgoing flow")
            if kind == "startEvent" and incoming[i]:
                raise ValueError("start has incoming flow")
            if kind != "endEvent" and not outgoing[i]:
                raise ValueError("non-terminal node has no outgoing flow")
            if kind == "exclusiveGateway" and outgoing[i]:
                default = n.get("default")
                if (
                    default not in outgoing[i]
                    or flows[default].find("bpmn:conditionExpression", NS) is not None
                ):
                    raise ValueError("invalid default")
                if any(
                    flows[f].find("bpmn:conditionExpression", NS) is None
                    for f in outgoing[i]
                    if f != default
                ):
                    raise ValueError("unguarded alternative")
            if questions is not None and kind == "userTask":
                ref = n.find("bpmn:extensionElements/sfsm:questionRef", NS)
                if (
                    ref is None
                    or ref.get("href", "").split("#/questions/")[-1]
                    not in questions["questions"]
                ):
                    raise ValueError("missing question metadata")
    shapes = root.findall(".//bpmndi:BPMNShape", NS)
    edges = root.findall(".//bpmndi:BPMNEdge", NS)
    if (
        len(shapes) != len(nodes)
        or {s.get("bpmnElement") for s in shapes} != nodes.keys()
    ):
        raise ValueError("shape coverage mismatch")
    if (
        len(edges) != len(flows)
        or {e.get("bpmnElement") for e in edges} != flows.keys()
    ):
        raise ValueError("edge coverage mismatch")
    planes = root.findall(".//bpmndi:BPMNPlane", NS)
    if len(planes) != len(processes) or {p.get("bpmnElement") for p in planes} != {
        p.get("id") for p in processes
    }:
        raise ValueError("process plane coverage mismatch")
    boxes = {}
    for plane in planes:
        pid = plane.get("bpmnElement")
        for shape in plane.findall("bpmndi:BPMNShape", NS):
            nid = shape.get("bpmnElement")
            if scopes[nid] != pid:
                raise ValueError("shape in wrong plane")
            b = shape.find("dc:Bounds", NS)
            if b is None:
                raise ValueError("missing bounds")
            box = tuple(float(b.get(k)) for k in ["x", "y", "width", "height"])
            if not all(math.isfinite(v) and v >= 0 for v in box) or min(box[2:]) <= 0:
                raise ValueError("invalid bounds")
            boxes[nid] = box
        for edge in plane.findall("bpmndi:BPMNEdge", NS):
            f = flows[edge.get("bpmnElement")]
            if scopes[f.get("sourceRef")] != pid:
                raise ValueError("edge in wrong plane")
    for edge in edges:
        points = [
            (float(p.get("x")), float(p.get("y")))
            for p in edge.findall("di:waypoint", NS)
        ]
        if len(points) < 2 or not all(
            math.isfinite(v) and v >= 0 for pt in points for v in pt
        ):
            raise ValueError("invalid waypoints")
        f = flows[edge.get("bpmnElement")]
        for nid, (a, b) in [
            (f.get("sourceRef"), points[0]),
            (f.get("targetRef"), points[-1]),
        ]:
            x, y, w, h = boxes[nid]
            if not (
                x - 0.01 <= a <= x + w + 0.01
                and y - 0.01 <= b <= y + h + 0.01
                and min(abs(a - x), abs(a - x - w), abs(b - y), abs(b - y - h)) < 0.01
            ):
                raise ValueError("edge endpoint does not dock")
    for nid, n in nodes.items():
        if n.tag.endswith("boundaryEvent"):
            x, y, w, h = boxes[nid]
            tx, ty, tw, th = boxes[n.get("attachedToRef")]
            if not (tx <= x + w / 2 <= tx + tw and abs(y + h / 2 - (ty + th)) < 0.01):
                raise ValueError("boundary event not attached to task border")
    return {
        "processes": len(processes),
        "nodes": len(nodes),
        "flows": len(flows),
        "shapes": len(shapes),
        "edges": len(edges),
    }
