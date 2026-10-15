"""SFSM -> linked BPMN processes, using the Forms exporter's graph/DI layout.

No interpreter changes. JSON predicates and data mappings remain metadata;
call-activity outcome dispatch is explicitly separate from service-call errors.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from forms_bpmn.converter import (
    NS,
    Edge,
    Graph,
    Node,
    describe,
    el,
    layout,
    write_di,
    xml_id,
)

SFSM_NS = "urn:govuk:sfsm:bpmn:visualisation:v1"
NS["sfsm"] = SFSM_NS
ET.register_namespace("sfsm", SFSM_NS)


class UnsupportedSFSM(ValueError):
    pass


@dataclass
class Conversion:
    xml: str
    questions: dict
    report: dict
    graphs: dict[str, Graph]


KINDS = {
    "input": "userTask",
    "choice": "exclusiveGateway",
    "output": "task",
    "assign": "scriptTask",
    "invoke": "callActivity",
    "call": "serviceTask",
    "end": "endEvent",
}
FIELDS = {
    "input": {"type", "prompt", "schema", "assign", "next"},
    "choice": {"type", "rules", "default"},
    "output": {"type", "channel", "message", "next"},
    "assign": {"type", "set", "next"},
    "invoke": {"type", "process", "input", "assign", "catch", "next"},
    "call": {
        "type",
        "method",
        "service",
        "url",
        "body",
        "idempotency_key",
        "assign",
        "capture",
        "catch",
        "next",
    },
    "end": {"type", "status", "outcome", "return"},
}


def sid_id(pid, sid):
    # Encoding the pair as JSON avoids ambiguity between process and state IDs.
    return xml_id(
        "state", json.dumps([pid, sid], separators=(",", ":"), ensure_ascii=False)
    )


def title(value):
    name = (
        re.sub(r"section(\d+)", r"Section \1:", value)
        .replace("_", " ")
        .strip()
        .capitalize()
    )
    for acronym in [
        "api",
        "hmrc",
        "dwp",
        "rti",
        "nino",
        "utr",
        "smp1",
        "matb1",
        "map",
        "ma1",
    ]:
        name = re.sub(
            r"\b" + acronym + r"\b", acronym.upper(), name, flags=re.IGNORECASE
        )
    return name


def label(sid, state):
    value = re.sub(r"^(prompt|branch|evaluate|say|announce|invoke|run)_", "", sid)
    if state["type"] == "input":
        line = state["prompt"].splitlines()[0].strip()
        return line if len(line) <= 100 else title(value)
    if state["type"] == "choice":
        return title(value) + "?"
    if state["type"] == "end":
        return title(
            state.get("outcome")
            or ("Return" if state.get("status") == "success" else state["status"])
        )
    return title(value)


def guarded(predicate, previous):
    return (
        copy.deepcopy(predicate)
        if not previous
        else {
            "op": "and",
            "all": [
                copy.deepcopy(predicate),
                {
                    "op": "not",
                    "condition": {"op": "or", "any": copy.deepcopy(previous)},
                },
            ],
        }
    )


def check_source(source):
    if not isinstance(source, dict):
        raise UnsupportedSFSM("definition must be a JSON object")
    if source.get("schema") != "sfsm/0.2":
        raise UnsupportedSFSM("only sfsm/0.2 definitions are supported")
    processes = source.get("processes")
    if (
        not isinstance(processes, dict)
        or not processes
        or source.get("entry") not in processes
    ):
        raise UnsupportedSFSM("missing processes or invalid entry process")
    for pid, process in processes.items():
        if not isinstance(process, dict):
            raise UnsupportedSFSM(f"{pid}: process must be an object")
        if not isinstance(process.get("vars", {}), dict):
            raise UnsupportedSFSM(f"{pid}: vars must be an object")
        states = process.get("states")
        if not isinstance(states, dict) or process.get("start") not in states:
            raise UnsupportedSFSM(f"{pid}: missing states or invalid start")
        for sid, s in states.items():
            if not isinstance(s, dict):
                raise UnsupportedSFSM(f"{pid}/{sid}: state must be an object")
            kind = s.get("type")
            if kind not in KINDS:
                raise UnsupportedSFSM(f"{pid}/{sid}: unsupported state type {kind!r}")
            unknown = set(s) - FIELDS[kind]
            if unknown:
                raise UnsupportedSFSM(
                    f"{pid}/{sid}: unsupported state fields {sorted(unknown)}"
                )
            required = {
                "input": {"prompt", "schema", "assign", "next"},
                "choice": {"rules", "default"},
                "output": {"message", "next"},
                "assign": {"set", "next"},
                "invoke": {"process", "next"},
                "call": {"method", "service", "url", "next"},
                "end": {"status"},
            }[kind]
            if required - set(s):
                raise UnsupportedSFSM(
                    f"{pid}/{sid}: missing fields {sorted(required - set(s))}"
                )
            targets = []
            if kind == "choice":
                if not isinstance(s.get("rules"), list) or "default" not in s:
                    raise UnsupportedSFSM(f"{pid}/{sid}: invalid choice")
                for rule in s["rules"]:
                    if (
                        set(rule) != {"when", "next"}
                        or not isinstance(rule["when"], dict)
                        or "op" not in rule["when"]
                    ):
                        raise UnsupportedSFSM(f"{pid}/{sid}: invalid choice rule")
                targets = [r["next"] for r in s["rules"]] + [s["default"]]
            elif kind != "end":
                if "next" not in s:
                    raise UnsupportedSFSM(f"{pid}/{sid}: missing next")
                targets = [s["next"]]
            if kind == "invoke" and s.get("process") not in processes:
                raise UnsupportedSFSM(f"{pid}/{sid}: unknown invoked process")
            if kind == "input" and (
                not isinstance(s.get("schema"), dict)
                or not isinstance(s.get("prompt"), str)
            ):
                raise UnsupportedSFSM(f"{pid}/{sid}: missing input schema/prompt")
            if kind == "end" and "status" not in s:
                raise UnsupportedSFSM(f"{pid}/{sid}: missing end status")
            catches = s.get("catch", [])
            if not isinstance(catches, list):
                raise UnsupportedSFSM(f"{pid}/{sid}: invalid catch list")
            for catch in catches:
                if set(catch) != {"on", "next"} or not isinstance(catch["on"], str):
                    raise UnsupportedSFSM(f"{pid}/{sid}: invalid catch")
                if kind == "call" and catch["on"] != "any":
                    raise UnsupportedSFSM(
                        f"{pid}/{sid}: interpreter only handles service-call catch on any"
                    )
                targets.append(catch["next"])
            if any(t not in states for t in targets):
                raise UnsupportedSFSM(f"{pid}/{sid}: missing transition target")
    # A recursive invocation would need an explicit recursion visualisation.
    active = set()
    seen = set()

    def visit(pid):
        if pid in active:
            raise UnsupportedSFSM(f"recursive process invocation: {pid}")
        if pid in seen:
            return
        active.add(pid)
        for s in processes[pid]["states"].values():
            if s["type"] == "invoke":
                visit(s["process"])
        active.remove(pid)
        seen.add(pid)

    for pid in processes:
        visit(pid)


def section_announcements(pid, process):
    """Only explicit, singly-entered announce_sectionN -> sectionN calls fold.

    This is a visual summary, not deletion of a source output instruction.
    Other messages, channels, branching and shared-entry calls remain explicit.
    """
    states = process["states"]
    incoming = {sid: [] for sid in states}
    for sid, state in states.items():
        targets = [state["next"]] if "next" in state else []
        targets += [r["next"] for r in state.get("rules", [])]
        targets += [r["next"] for r in state.get("catch", [])]
        targets += [state["default"]] if "default" in state else []
        for target in targets:
            incoming[target].append(sid)
    folded = {}
    for sid, state in states.items():
        match = re.fullmatch(r"announce_section(\d+)", sid)
        target = states.get(state.get("next"), {})
        if (
            match
            and state["type"] == "output"
            and state.get("channel") == "transcript"
            and target.get("type") == "invoke"
            and re.match(r"section" + match[1] + r"(?:_|$)", target["process"])
            and incoming[state["next"]] == [sid]
            and process["start"] != state["next"]
        ):
            folded[sid] = state["next"]
    return folded


def build_process(pid, process, *, fold_announcements=True):
    nodes = {}
    edges = []
    attachments = {}
    states = process["states"]
    folded = section_announcements(pid, process) if fold_announcements else {}
    start = xml_id("start", pid)
    nodes[start] = Node(start, "startEvent", "Start")
    edges.append(Edge(xml_id("entry", pid), start, sid_id(pid, process["start"])))

    def flow(sid, suffix, a, target, name="", predicate=None, default=False):
        edges.append(
            Edge(
                xml_id("flow", json.dumps([pid, sid, suffix], separators=(",", ":"))),
                a,
                sid_id(pid, target),
                name,
                predicate,
                default,
            )
        )

    for sid, s in states.items():
        nid = sid_id(pid, sid)
        nodes[nid] = Node(nid, KINDS[s["type"]], label(sid, s), sid, copy.deepcopy(s))
        if s["type"] == "choice":
            previous = []
            for i, rule in enumerate(s["rules"]):
                name = describe(rule["when"], {}) + (
                    " (if no earlier rule matches)" if previous else ""
                )
                flow(
                    sid,
                    f"rule_{i}",
                    nid,
                    rule["next"],
                    name,
                    guarded(rule["when"], previous),
                )
                previous.append(rule["when"])
            flow(sid, "default", nid, s["default"], "Otherwise", default=True)
        elif s["type"] == "invoke" and s.get("catch"):
            gateway = xml_id("outcome", nid)
            nodes[gateway] = Node(
                gateway,
                "exclusiveGateway",
                "Returned outcome?",
                state={"invoke_state": sid},
            )
            edges.append(Edge(xml_id("returned", nid), nid, gateway))
            previous = []
            # These predicates refer to a display-only returned-result envelope,
            # not an implicit variable in the SFSM runtime.
            for i, catch in enumerate(s["catch"]):
                predicate = (
                    {"op": "returned_outcome", "value": catch["on"]}
                    if catch["on"] != "any"
                    else {"op": "always"}
                )
                flow(
                    sid,
                    f"catch_{i}",
                    gateway,
                    catch["next"],
                    catch["on"],
                    guarded(predicate, previous),
                )
                previous.append(predicate)
            flow(
                sid, "next", gateway, s["next"], "Other returned outcome", default=True
            )
        elif s["type"] != "end":
            flow(sid, "next", nid, s["next"])
        if s["type"] == "call" and s.get("catch"):
            # Runtime takes the first catch on any. Later any handlers cannot run.
            event = xml_id("error", nid)
            nodes[event] = Node(
                event,
                "boundaryEvent",
                "API error",
                state={"attached_to": nid, "catch": s["catch"][0]},
            )
            attachments[event] = nid
            flow(sid, "error", event, s["catch"][0]["next"], "API failed")
    # Redirect incoming flows to the call while retaining their IDs/guards.
    for edge in edges:
        for announcement, call in folded.items():
            if edge.target == sid_id(pid, announcement):
                edge.target = sid_id(pid, call)
    edges = [e for e in edges if e.source not in {sid_id(pid, sid) for sid in folded}]
    for sid in folded:
        del nodes[sid_id(pid, sid)]
    graph = Graph(nodes, edges, start)
    # Invisible layout-only links keep error-handler paths ranked with their
    # tasks. They are removed before XML/DI is written: boundary events have no
    # incoming sequence flow in BPMN.
    links = [
        Edge(xml_id("layout", event), task, event)
        for event, task in attachments.items()
    ]
    graph.edges.extend(links)
    layout(graph)
    graph.edges = [e for e in graph.edges if e not in links]
    for event, task in attachments.items():
        n, t = nodes[event], nodes[task]
        n.width = n.height = 40
        n.x = t.x + t.width - 20
        n.y = t.y + t.height - 20
        for edge in graph.edges:
            if edge.source != event:
                continue
            target = nodes[edge.target]
            top, bottom = (
                min(t.y, target.y),
                max(t.y + t.height, target.y + target.height),
            )
            crossed = [
                node
                for node in nodes.values()
                if node.y <= bottom and node.y + node.height >= top
            ]
            lane = max(node.x + node.width for node in crossed) + 65
            source_y = t.y + t.height + 75
            target_y = target.y - 55
            edge.points = [
                (n.x + 20, n.y + 40),
                (n.x + 20, source_y),
                (lane, source_y),
                (lane, target_y),
                (target.x + target.width / 2, target_y),
                (target.x + target.width / 2, target.y),
            ]
            edge.label = (lane + 12, (source_y + target_y) / 2 - 20, 120, 40)
            graph.width = max(graph.width, lane + 172)
    # Reachability includes boundary events attached to reachable service tasks.
    seen = set()
    queue = [start]
    while queue:
        n = queue.pop()
        if n in seen:
            continue
        seen.add(n)
        queue.extend(e.target for e in edges if e.source == n)
        queue.extend(event for event, task in attachments.items() if task == n)
    unreachable = [
        sid for sid in states if sid_id(pid, folded.get(sid, sid)) not in seen
    ]
    return graph, unreachable, folded


def write_process(root, pid, process, graph, question_file, folded):
    owner = el(
        root,
        "bpmn:process",
        id=xml_id("process", pid),
        name=title(pid),
        isExecutable="false",
    )
    el(
        owner,
        "bpmn:documentation",
        "Visualisation only. Conditions, mappings and original SFSM are retained in metadata; no engine compatibility or service execution is implied.",
    )
    ext = el(owner, "bpmn:extensionElements")
    el(ext, "sfsm:processRef", processId=pid)
    el(ext, "sfsm:variables", json.dumps(process.get("vars", {}), ensure_ascii=False))
    for n in graph.nodes.values():
        attrs = {"id": n.id, "name": n.name}
        default = next(
            (e.id for e in graph.edges if e.source == n.id and e.default), None
        )
        if default:
            attrs["default"] = default
        if n.kind == "callActivity":
            attrs["calledElement"] = xml_id("process", n.state["process"])
        if n.kind == "boundaryEvent":
            attrs.update(attachedToRef=n.state["attached_to"], cancelActivity="true")
        element = el(owner, "bpmn:" + n.kind, **attrs)
        ext = el(element, "bpmn:extensionElements")
        if n.state_id:
            el(ext, "sfsm:stateRef", processId=pid, stateId=n.state_id)
        el(ext, "sfsm:state", json.dumps(n.state, ensure_ascii=False))
        for sid, call in folded.items():
            if call == n.state_id:
                announcement = el(ext, "sfsm:announcement", id=sid_id(pid, sid))
                el(announcement, "sfsm:stateRef", processId=pid, stateId=sid)
                el(
                    announcement,
                    "sfsm:state",
                    json.dumps(process["states"][sid], ensure_ascii=False),
                )
        if n.kind == "userTask":
            el(
                ext,
                "sfsm:questionRef",
                href=question_file + "#/questions/" + n.id,
                sourceStepId=pid + "/" + n.state_id,
                generated="false",
                assign=n.state.get("assign", ""),
            )
        for e in graph.edges:
            if e.target == n.id:
                el(element, "bpmn:incoming", e.id)
        for e in graph.edges:
            if e.source == n.id:
                el(element, "bpmn:outgoing", e.id)
        if n.kind == "boundaryEvent":
            el(element, "bpmn:errorEventDefinition", id=xml_id("definition", n.id))
    for e in graph.edges:
        item = el(
            owner,
            "bpmn:sequenceFlow",
            id=e.id,
            sourceRef=e.source,
            targetRef=e.target,
            **({"name": e.name} if e.name else {}),
        )
        if e.predicate is not None:
            expr = el(
                item,
                "bpmn:conditionExpression",
                json.dumps(e.predicate, ensure_ascii=False),
                language="urn:govuk:sfsm:bpmn:condition-json:v1",
            )
            expr.set("{" + NS["xsi"] + "}type", "bpmn:tFormalExpression")
    return owner


def convert_sfsm(
    source, *, question_file="journey.questions.json", fold_announcements=True
):
    check_source(source)
    source = copy.deepcopy(source)
    root = ET.Element(
        "{" + NS["bpmn"] + "}definitions",
        {"id": xml_id("definitions", source["id"]), "targetNamespace": SFSM_NS},
    )
    graphs = {}
    reports = []
    warnings = [
        "Visualisation only. JSON conditions and data mappings are not executable BPMN expressions.",
        "Call-activity catches dispatch returned outcomes, independent of status. API-error catches use interrupting error boundary events.",
        "An unhandled child outcome continues to invoke.next, matching SFSM; it does not automatically become a BPMN error.",
        "Short labels are derived from state IDs or the first prompt line; full source wording is retained in the inspector.",
        "Output tasks reproduce source messages; a submission announcement does not imply a submission API call.",
    ]
    order = [source["entry"]] + [p for p in source["processes"] if p != source["entry"]]
    for pid in order:
        p = source["processes"][pid]
        g, unreachable, folded = build_process(
            pid, p, fold_announcements=fold_announcements
        )
        graphs[pid] = g
        write_process(root, pid, p, g, question_file, folded)
        reports.append(
            {
                "id": pid,
                "bpmn_id": xml_id("process", pid),
                "name": title(pid),
                "state_count": len(p["states"]),
                "question_count": sum(
                    s["type"] == "input" for s in p["states"].values()
                ),
                "unreachable": unreachable,
                "folded_announcements": folded,
            }
        )
        if unreachable:
            warnings.append(
                f"{pid}: unreachable source states retained as disconnected nodes: "
                + ", ".join(unreachable)
            )
        for sid, s in p["states"].items():
            if s["type"] == "call" and len(s.get("catch", [])) > 1:
                warnings.append(
                    f"{pid}/{sid}: later catch-on-any handlers are unreachable; only the first is drawn."
                )
    # All processes and their diagrams live in one portable BPMN file. The viewer
    # selects a plane; calledElement references resolve within these definitions.
    for pid, g in graphs.items():
        diagram = el(
            root, "bpmndi:BPMNDiagram", id=xml_id("diagram", pid), name=title(pid)
        )
        plane = el(
            diagram,
            "bpmndi:BPMNPlane",
            id=xml_id("plane", pid),
            bpmnElement=xml_id("process", pid),
        )
        write_di(plane, g)
    questions = {
        "schema": "sfsm-bpmn-questions/1",
        "source_sfsm": source,
        "questions": {
            sid_id(pid, sid): {
                "source_step_id": pid + "/" + sid,
                "process_id": pid,
                "state_id": sid,
                "generated": False,
                "prompt": s["prompt"],
                "schema": s["schema"],
                "assign": s.get("assign"),
            }
            for pid, p in source["processes"].items()
            for sid, s in p["states"].items()
            if s["type"] == "input"
        },
    }
    report = {
        "schema": "sfsm-bpmn-report/1",
        "model_id": source["id"],
        "name": title(source["id"].split(".")[-1]),
        "mode": "sfsm",
        "entry_bpmn_id": xml_id("process", source["entry"]),
        "question_count": len(questions["questions"]),
        "processes": reports,
        "decomposition": [],
        "warnings": warnings,
    }
    ET.indent(root)
    return Conversion(
        ET.tostring(root, encoding="unicode", xml_declaration=True),
        questions,
        report,
        graphs,
    )
