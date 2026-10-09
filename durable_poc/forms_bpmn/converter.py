"""Forms -> existing SFSM compiler -> non-executable BPMN with diagram interchange.

No second Forms routing parser. Conditions use the SFSM JSON predicate vocabulary,
with earlier rules explicitly excluded to preserve first-match semantics in BPMN.
"""

from __future__ import annotations

import copy
import json
import re
import textwrap
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from forms_adapter import UnsupportedForm, compile_form, normalise_form
from forms_adapter.compiler import ORDINARY_SCALARS

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "forms": "urn:govuk:forms:bpmn:visualisation:v1",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def el(parent, tag, text=None, **attrs):
    prefix, name = tag.split(":")
    item = ET.SubElement(
        parent, f"{{{NS[prefix]}}}{name}", {k: str(v) for k, v in attrs.items()}
    )
    item.text = text
    return item


def xml_id(prefix: str, value: str) -> str:
    # Injective encoding; escape underscore too, so a literal _2f cannot collide.
    return (
        prefix
        + "_"
        + "".join(
            c if re.fullmatch(r"[A-Za-z0-9]", c) else f"_{ord(c):x}_" for c in value
        )
    )


@dataclass
class Node:
    id: str
    kind: str
    name: str
    state_id: str | None = None
    state: dict = field(default_factory=dict)
    children: Graph | None = None
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0


@dataclass
class Edge:
    id: str
    source: str
    target: str
    name: str = ""
    predicate: dict | None = None
    default: bool = False
    points: list[tuple[float, float]] = field(default_factory=list)
    label: tuple[float, float, float, float] | None = None


@dataclass
class Graph:
    nodes: dict[str, Node]
    edges: list[Edge]
    start: str
    width: float = 0
    height: float = 0
    source_ids: set[str] = field(default_factory=set)


@dataclass
class Conversion:
    xml: str
    questions: dict
    graph: Graph
    report: dict


def describe(predicate: dict, positions: dict[str, Any]) -> str:
    op, path = predicate.get("op"), predicate.get("path", "")
    qid = path.removeprefix("answers.")
    label = (
        f"Q{positions[qid]}"
        if qid in positions
        else ("Add another answer" if path.endswith(".more") else path)
    )
    if op == "is_true":
        return f"{label}: Yes"
    if op == "is_false":
        return f"{label}: No"
    if op in ("eq", "contains"):
        value = predicate.get("value")
        rendered = (
            json.dumps(value, ensure_ascii=False)
            if not isinstance(value, str)
            else value
        )
        return f"{label} {'includes' if op == 'contains' else '='} {rendered}"
    return json.dumps(predicate, ensure_ascii=False)


def build_graph(compiled: dict, positions: dict) -> Graph:
    states = compiled["processes"]["main"]["states"]
    nodes, edges = {}, []
    for sid, state in states.items():
        kind = {
            "input": "userTask",
            "choice": "exclusiveGateway",
            "assign": "scriptTask",
            "output": "task",
            "end": "endEvent",
        }.get(state["type"])
        if kind is None:
            raise UnsupportedForm(
                f"BPMN export does not support state type {state['type']!r}"
            )
        presentation = state.get("schema", {}).get("presentation", {})
        if state["type"] == "input":
            prefix = f"Q{positions[sid]} · " if sid in positions else ""
            name = prefix + state["prompt"].strip()
            if presentation.get("is_optional"):
                name += " (optional)"
        elif state["type"] == "choice":
            name = (
                "More answers?"
                if sid.endswith("__repeat_route")
                else "Skipped?"
                if sid.endswith("__skip_route")
                else "Route answer"
            )
        elif state["type"] == "end":
            name = (
                "Answers collected"
                if sid == "end_form"
                else "Exit: " + state.get("outcome", "offramp")
            )
        elif state["type"] == "output":
            name = "Show exit: " + state["message"].splitlines()[0]
        else:
            name = "Append answer to collection"
        nid = xml_id("state", sid)
        nodes[nid] = Node(nid, kind, name, sid, state)
        if state["type"] == "choice":
            previous = []
            for i, rule in enumerate(state["rules"]):
                predicate = copy.deepcopy(rule["when"])
                # BPMN has no portable 'first matching outgoing flow' rule.
                guard = (
                    predicate
                    if not previous
                    else {
                        "op": "and",
                        "all": [
                            predicate,
                            {
                                "op": "not",
                                "condition": {
                                    "op": "or",
                                    "any": copy.deepcopy(previous),
                                },
                            },
                        ],
                    }
                )
                name = describe(predicate, positions)
                if previous:
                    name += " (if no earlier rule matches)"
                edges.append(
                    Edge(
                        xml_id("flow", sid + f"__rule_{i + 1}"),
                        nid,
                        xml_id("state", rule["next"]),
                        name,
                        guard,
                    )
                )
                previous.append(predicate)
            edges.append(
                Edge(
                    xml_id("flow", sid + "__default"),
                    nid,
                    xml_id("state", state["default"]),
                    "Otherwise",
                    default=True,
                )
            )
        elif state["type"] != "end":
            edges.append(
                Edge(
                    xml_id("flow", sid + "__next"), nid, xml_id("state", state["next"])
                )
            )
    start = xml_id("start", compiled["id"])
    nodes[start] = Node(start, "startEvent", "Start")
    edges.insert(
        0,
        Edge(
            xml_id("flow", compiled["id"] + "__start"),
            start,
            xml_id("state", compiled["processes"]["main"]["start"]),
        ),
    )
    graph = Graph(nodes, edges, start)
    reached = reachable(graph, start)
    missing = set(nodes) - reached
    # The compiler always adds a normal completion, even if every real path
    # exits early. Omit that unused generated end, never source questions.
    for nid in list(missing):
        if nodes[nid].state_id == "end_form":
            del nodes[nid]
            missing.remove(nid)
    if missing:
        # A faithful visual spike should expose malformed/unreachable source
        # rather than emit misleading floating tasks or silently prune them.
        raise UnsupportedForm(
            "unreachable compiled states: "
            + ", ".join(sorted(nodes[n].state_id or n for n in missing))
        )
    return graph


def reachable(graph: Graph, start: str, stop: str | None = None) -> set[str]:
    adj = defaultdict(list)
    for edge in graph.edges:
        adj[edge.source].append(edge.target)
    seen, queue = set(), [start]
    while queue:
        n = queue.pop()
        if n == stop or n in seen:
            continue
        seen.add(n)
        queue.extend(adj[n])
    return seen


def group_region(
    graph: Graph,
    members: set[str],
    entry: str,
    continuation: str,
    name: str,
    reason: str,
) -> str:
    """Replace an SESE region with an expanded subprocess, with local start/end.

    Original source node/flow IDs survive. Cross-boundary flows are redirected;
    no sequence flow crosses BPMN scopes. Parent has exactly one continuation.
    """
    nid = xml_id("subprocess", graph.nodes[entry].state_id or entry)
    start, end = nid + "_start", nid + "_end"
    children = {n: graph.nodes[n] for n in graph.nodes if n in members}
    children[start] = Node(start, "startEvent", "Start collection")
    children[end] = Node(end, "endEvent", "Continue")
    inner = [Edge(nid + "_entry", start, entry)]
    outer = []
    for edge in graph.edges:
        if edge.source in members:
            if edge.target not in members:
                if edge.target != continuation:
                    raise UnsupportedForm(
                        "subprocess region has multiple continuations"
                    )
                edge.target = end
            inner.append(edge)
        else:
            if edge.target in members:
                if edge.target != entry:
                    raise UnsupportedForm("subprocess region has multiple entries")
                edge.target = nid
            outer.append(edge)
    outer.append(Edge(nid + "_continuation", nid, continuation))
    for n in members:
        del graph.nodes[n]
    graph.nodes[nid] = Node(
        nid,
        "subProcess",
        name,
        state={
            "reason": reason,
            "members": sorted(members),
            "entry": entry,
            "continuation": continuation,
        },
        children=Graph(children, inner, start),
    )
    graph.edges = outer
    return nid


def decompose(graph: Graph, questions: list) -> list[dict]:
    groups = []
    # Repetition is explicit source metadata, a stronger boundary than headings.
    for q in questions:
        if not q.data.get("is_repeatable"):
            continue
        members = {
            nid
            for nid, n in graph.nodes.items()
            if n.state_id == q.id
            or n.state_id
            in {
                q.id + suffix
                for suffix in ("__append", "__more", "__repeat_route", "__skip_route")
            }
        }
        entry = xml_id("state", q.id)
        outgoing = {
            e.target
            for e in graph.edges
            if e.source in members and e.target not in members
        }
        incoming = {
            e.target
            for e in graph.edges
            if e.source not in members and e.target in members
        }
        if len(outgoing) == 1 and incoming == {entry}:
            nid = group_region(
                graph,
                members,
                entry,
                next(iter(outgoing)),
                "Repeat collection · " + q.data["question_text"].strip(),
                "explicit is_repeatable",
            )
            groups.append(
                {"id": nid, "reason": "explicit is_repeatable", "question_ids": [q.id]}
            )
    # Conservative acyclic SESE regions only. A structural region is not an
    # assertion of reusable business capability, and no names are inferred.
    adj = {n: [e.target for e in graph.edges if e.source == n] for n in graph.nodes}
    post = {n: set(graph.nodes) for n in graph.nodes}
    terminals = {n for n in adj if not adj[n]}
    for n in terminals:
        post[n] = {n}
    for _ in range(len(adj) * 2):
        changed = False
        for n, successors in adj.items():
            if not successors:
                continue
            new = {n} | set.intersection(*(post[t] for t in successors))
            if new != post[n]:
                post[n], changed = new, True
        if not changed:
            break
    candidates = []
    for q in questions:
        entry = xml_id("state", q.id)
        if entry not in graph.nodes or len(adj[entry]) != 1:
            continue
        split = adj[entry][0]
        if graph.nodes[split].kind != "exclusiveGateway" or len(set(adj[split])) < 2:
            continue
        # Nearest postdominator is itself postdominated by all farther ones.
        options = post[split] - {split, entry}
        joins = [j for j in options if options <= post[j]]
        if len(joins) != 1:
            continue
        join = joins[0]
        members = reachable(graph, entry, join)
        # Every path must terminate at the join, no backedges/embedded groups.
        if any(
            graph.nodes[n].children or graph.nodes[n].kind == "endEvent"
            for n in members
        ):
            continue
        incoming = {
            e.target
            for e in graph.edges
            if e.source not in members and e.target in members
        }
        outgoing = {
            e.target
            for e in graph.edges
            if e.source in members and e.target not in members
        }
        if (
            incoming != {entry}
            or outgoing != {join}
            or any(e.target == entry for e in graph.edges if e.source in members)
        ):
            continue
        if not is_acyclic(members, graph.edges):
            continue
        qids = [q2.id for q2 in questions if xml_id("state", q2.id) in members]
        # One question + gateway is just a decision, not decomposition.
        if len(qids) < 3:
            continue
        candidates.append((members, entry, join, qids, q.data["question_text"].strip()))
    for members, entry, join, qids, title in sorted(
        candidates, key=lambda c: -len(c[0])
    ):
        if not members <= graph.nodes.keys() or join not in graph.nodes:
            continue
        nid = group_region(
            graph,
            members,
            entry,
            join,
            "Routing region · " + title,
            "acyclic single-entry/single-continuation routing region",
        )
        groups.append(
            {
                "id": nid,
                "reason": "acyclic single-entry/single-continuation routing region",
                "question_ids": qids,
            }
        )
    return groups


def is_acyclic(members: set[str], edges: list[Edge]) -> bool:
    indegree = {n: 0 for n in members}
    adj = defaultdict(list)
    for e in edges:
        if e.source in members and e.target in members:
            indegree[e.target] += 1
            adj[e.source].append(e.target)
    queue = deque(n for n in members if not indegree[n])
    count = 0
    while queue:
        n = queue.popleft()
        count += 1
        for t in adj[n]:
            indegree[t] -= 1
            if not indegree[t]:
                queue.append(t)
    return count == len(members)


def add_merges(graph: Graph) -> None:
    """Make alternative-path convergence explicit, including repeat returns."""
    for n in list(graph.nodes.values()):
        if n.children:
            add_merges(n.children)
        incoming = [e for e in graph.edges if e.target == n.id]
        if len(incoming) < 2:
            continue
        mid = "merge_" + n.id
        graph.nodes[mid] = Node(mid, "exclusiveGateway", "Merge routes")
        for e in incoming:
            e.target = mid
        graph.edges.append(Edge(mid + "_next", mid, n.id))


def layout(graph: Graph) -> None:
    """Deterministic top-down layered layout; loops get an exterior return lane.

    No folded snake of sequential questions: it would suggest false branching.
    Variable task heights retain full labels. Expanded children size their box.
    """
    for n in graph.nodes.values():
        if n.children:
            layout(n.children)
            n.width, n.height = n.children.width + 80, n.children.height + 140
        elif n.kind in {"startEvent", "endEvent"}:
            n.width, n.height = 40, 40
        elif n.kind == "exclusiveGateway":
            n.width, n.height = 50, 50
        else:
            n.width = 330
            n.height = max(90, 35 + 19 * len(textwrap.wrap(n.name, 37)))
    adj = defaultdict(list)
    for e in graph.edges:
        adj[e.source].append(e)
    visited, active, back = set(), set(), set()

    def visit(n):
        if n in visited:
            return
        active.add(n)
        for e in adj[n]:
            if e.target in active:
                back.add(e.id)
            else:
                visit(e.target)
        active.remove(n)
        visited.add(n)

    visit(graph.start)
    dag = [e for e in graph.edges if e.id not in back]
    indegree = {n: 0 for n in graph.nodes}
    parents = defaultdict(list)
    for e in dag:
        indegree[e.target] += 1
        parents[e.target].append(e.source)
    queue = deque(n for n in graph.nodes if not indegree[n])
    rank = {n: 0 for n in graph.nodes}
    while queue:
        n = queue.popleft()
        for e in adj[n]:
            if e.id in back:
                continue
            rank[e.target] = max(rank[e.target], rank[n] + 1)
            indegree[e.target] -= 1
            if not indegree[e.target]:
                queue.append(e.target)
    levels = defaultdict(list)
    for n in graph.nodes:
        levels[rank[n]].append(n)
    maxcols = max(map(len, levels.values()))
    col_width = max(n.width for n in graph.nodes.values()) + 130
    graph.width = maxcols * col_width + (120 if back else 0)
    y = 60
    for r in sorted(levels):
        ids = levels[r]
        ids.sort(
            key=lambda nid: (
                sum(graph.nodes[p].x + graph.nodes[p].width / 2 for p in parents[nid])
                / max(1, len(parents[nid])),
                list(graph.nodes).index(nid),
            )
        )
        height = max(graph.nodes[nid].height for nid in ids)
        for i, nid in enumerate(ids):
            node = graph.nodes[nid]
            node.x = (
                (graph.width - len(ids) * col_width) / 2
                + i * col_width
                + (col_width - node.width) / 2
            )
            node.y = y + (height - node.height) / 2
        y += height + 170
    graph.height = y - 90
    # Long skips and return loops use exterior lanes, so their lines cannot
    # pass through intervening tasks and falsely imply an extra connection.
    level_bottom = {
        r: max(graph.nodes[n].y + graph.nodes[n].height for n in ids)
        for r, ids in levels.items()
    }
    level_top = {r: min(graph.nodes[n].y for n in ids) for r, ids in levels.items()}
    special = [
        e for e in graph.edges if e.id in back or rank[e.target] > rank[e.source] + 1
    ]
    lane_base = graph.width + 35
    for i, e in enumerate(graph.edges):
        a, b = graph.nodes[e.source], graph.nodes[e.target]
        ax, bx = a.x + a.width / 2, b.x + b.width / 2
        sy, ty = a.y + a.height, b.y
        if e in special:
            # A skipped task may be directly below the source. Depart from an
            # off-centre task port, avoiding a shared vertical segment with an
            # unrelated branch entering that skipped task.
            if a.kind in {"userTask", "task", "scriptTask", "subProcess"}:
                ax = a.x + a.width * 0.85
            lane = lane_base + special.index(e) * 55
            top = level_bottom[rank[e.source]] + 35 + (i % 4) * 20
            bottom = level_top[rank[e.target]] - 55
            e.points = [
                (ax, sy),
                (ax, top),
                (lane, top),
                (lane, bottom),
                (bx, bottom),
                (bx, ty),
            ]
            lx, ly = lane + 12, top + 18
        else:
            mid = level_bottom[rank[e.source]] + 35 + (i % 4) * 20
            e.points = (
                [(ax, sy), (ax, mid), (bx, mid), (bx, ty)]
                if abs(ax - bx) > 1
                else [(ax, sy), (bx, ty)]
            )
            lx, ly = (bx - 155 if abs(ax - bx) > 1 else ax + 15), mid + 12
        if e.name:
            lines = textwrap.wrap(e.name, 43)
            e.label = (lx, ly, 310, max(25, 18 * len(lines)))
    # Include exterior lanes and all labels in the subprocess/preview extents.
    graph.width = max(
        [
            graph.width,
            *(x + 40 for e in graph.edges for x, y in e.points),
            *(e.label[0] + e.label[2] + 20 for e in graph.edges if e.label),
        ]
    )


def write_scope(parent, graph: Graph, sidecar: str) -> None:
    for n in graph.nodes.values():
        attrs = {"id": n.id, "name": n.name}
        defaults = [e.id for e in graph.edges if e.source == n.id and e.default]
        if defaults:
            attrs["default"] = defaults[0]
        element = el(parent, "bpmn:" + n.kind, **attrs)
        if n.state_id or n.children:
            extension = el(element, "bpmn:extensionElements")
            if n.state_id:
                el(extension, "forms:stateRef", stateId=n.state_id)
                # Store portable process semantics, not UI details, in XML.
                if n.kind == "userTask":
                    el(
                        extension,
                        "forms:questionRef",
                        href=sidecar + "#/questions/" + n.id,
                        sourceStepId=n.state.get("schema", {})
                        .get("presentation", {})
                        .get("repeat_for_step_id")
                        or n.state.get("schema", {})
                        .get("presentation", {})
                        .get("step_id", n.state_id),
                        generated=str(n.state_id not in graph.source_ids).lower(),
                        assign=n.state.get("assign", ""),
                    )
                else:
                    el(
                        extension,
                        "forms:state",
                        json.dumps(n.state, ensure_ascii=False),
                    )
            if n.children:
                el(
                    extension,
                    "forms:decomposition",
                    json.dumps(n.state, ensure_ascii=False),
                )
        for e in graph.edges:
            if e.target == n.id:
                el(element, "bpmn:incoming", e.id)
        for e in graph.edges:
            if e.source == n.id:
                el(element, "bpmn:outgoing", e.id)
        if n.children:
            write_scope(element, n.children, sidecar)
    for e in graph.edges:
        element = el(
            parent,
            "bpmn:sequenceFlow",
            id=e.id,
            sourceRef=e.source,
            targetRef=e.target,
            **({"name": e.name} if e.name else {}),
        )
        if e.predicate is not None:
            expr = el(
                element,
                "bpmn:conditionExpression",
                json.dumps(e.predicate, ensure_ascii=False),
                language="urn:govuk:sfsm:predicate-json:v1",
            )
            expr.set(f"{{{NS['xsi']}}}type", "bpmn:tFormalExpression")


def write_di(plane, graph: Graph, dx=0, dy=0) -> None:
    for n in graph.nodes.values():
        shape = el(
            plane,
            "bpmndi:BPMNShape",
            id="di_" + n.id,
            bpmnElement=n.id,
            **({"isExpanded": "true"} if n.children else {}),
        )
        el(shape, "dc:Bounds", x=n.x + dx, y=n.y + dy, width=n.width, height=n.height)
        if n.kind in {"startEvent", "endEvent", "exclusiveGateway"}:
            label = el(shape, "bpmndi:BPMNLabel")
            el(
                label,
                "dc:Bounds",
                x=n.x + dx - 105,
                y=n.y + dy + n.height + 8,
                width=n.width + 210,
                height=40,
            )
        if n.children:
            write_di(plane, n.children, n.x + dx + 40, n.y + dy + 95)
    for e in graph.edges:
        edge = el(plane, "bpmndi:BPMNEdge", id="di_" + e.id, bpmnElement=e.id)
        for x, y in e.points:
            el(edge, "di:waypoint", x=x + dx, y=y + dy)
        if e.label:
            x, y, w, h = e.label
            label = el(edge, "bpmndi:BPMNLabel")
            el(label, "dc:Bounds", x=x + dx, y=y + dy, width=w, height=h)


def convert_form(
    export: dict[str, Any], *, mode="flat", question_file="questions.json"
) -> Conversion:
    if mode not in {"flat", "auto"}:
        raise ValueError("mode must be flat or auto")
    content, source_questions = normalise_form(export)
    if content.get("payment_url"):
        raise UnsupportedForm(
            "payment_url: SFSM payment is simulated; no faithful payment process is available"
        )
    for q in source_questions:
        if q.data.get("answer_type") not in ORDINARY_SCALARS | {"selection", "file"}:
            raise UnsupportedForm(
                f"{q.id}: unknown answer_type {q.data.get('answer_type')!r}"
            )
    compiled = compile_form(export)
    positions = {q.id: q.position for q in source_questions}
    graph = build_graph(compiled, positions)
    sidecar = {
        "schema": "govuk-forms-bpmn-questions/1",
        "form_id": int(content.get("form_id") or export["form_id"]),
        "source_export": copy.deepcopy(export),
        "questions": {
            xml_id("state", sid): {
                "source_step_id": sid
                if sid in positions
                else state["schema"]["presentation"].get("repeat_for_step_id"),
                "generated": sid not in positions,
                "schema": copy.deepcopy(state["schema"]),
                "assign": state["assign"],
            }
            for sid, state in compiled["processes"]["main"]["states"].items()
            if state["type"] == "input"
        },
    }
    groups = decompose(graph, source_questions) if mode == "auto" else []

    def mark(g):
        g.source_ids = set(positions)
        for n in g.nodes.values():
            if n.children:
                mark(n.children)

    mark(graph)
    add_merges(graph)
    layout(graph)
    form_id = str(sidecar["form_id"])
    root = ET.Element(
        f"{{{NS['bpmn']}}}definitions",
        {"id": "definitions_forms_" + form_id, "targetNamespace": NS["forms"]},
    )
    process_id = "forms_" + form_id
    process = el(
        root,
        "bpmn:process",
        id=process_id,
        name=content.get("name", "").strip(),
        isExecutable="false",
    )
    el(
        process,
        "bpmn:documentation",
        "Visualisation only. Questions and original metadata: "
        + question_file
        + ". Conditions use SFSM predicate JSON. No submission, validation or payment execution is implied.",
    )
    write_scope(process, graph, question_file)
    diagram = el(root, "bpmndi:BPMNDiagram", id="diagram_" + process_id)
    plane = el(
        diagram, "bpmndi:BPMNPlane", id="plane_" + process_id, bpmnElement=process_id
    )
    write_di(plane, graph)
    ET.indent(root)
    xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    report = {
        "form_id": form_id,
        "mode": mode,
        "question_count": len(source_questions),
        "decomposition": groups,
        "warnings": [
            "Visualisation only; source validation/settings retained, not executed.",
            "Declarations, check-answers UI, submission and confirmation are not inferred; normal end means answers collected.",
            "SFSM primitive schemas are approximations for some source answer types; consult source_export.",
            "Routing regions are structural boundaries, not inferred reusable business services.",
        ],
    }
    return Conversion(xml, sidecar, graph, report)
