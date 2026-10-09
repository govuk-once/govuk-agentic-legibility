"""Test the exported BPMN as a graph, including traversal across subprocesses.

The XML walker is a test oracle, not a production execution engine. Expected
paths for the real examples are hand specified, independent of SFSM compilation.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from forms_adapter import UnsupportedForm, compile_form
from forms_bpmn.converter import NS, convert_form, xml_id
from forms_bpmn.validate import validate_bpmn
from src.paths import resolve_path, set_path
from src.predicates import evaluate

FIXTURES = Path(__file__).parent / "fixtures"


def source(fid):
    return json.loads((FIXTURES / f"{fid}.json").read_text())


def walk_xml(result, values, *, max_steps=200):
    """Follow alternative paths and return asked source IDs + terminal outcome."""
    root = ET.fromstring(result.xml)
    process = root.find("bpmn:process", NS)
    nodes = {e.get("id"): e for e in root.iter() if e.get("id")}
    owner = {e: p for p in root.iter() for e in p}
    context = {"answers": {}, "repeat": {}}
    current = process.find("bpmn:startEvent", NS)
    asked = []
    more = iter(values.get("__more__", []))
    for _ in range(max_steps):
        tag = current.tag.split("}")[-1]
        if tag == "subProcess":
            current = current.find("bpmn:startEvent", NS)
            continue
        ref = current.find("bpmn:extensionElements/forms:stateRef", NS)
        sid = ref.get("stateId") if ref is not None else None
        if tag == "userTask":
            definition = result.questions["questions"][current.get("id")]
            if definition["generated"]:
                value = next(more)
            else:
                asked.append(sid)
                value = values.get(sid, "sample")
            set_path(context, definition["assign"], value)
        state = current.find("bpmn:extensionElements/forms:state", NS)
        if tag == "scriptTask":
            assignments = json.loads(state.text)["set"]
            for path, expression in assignments.items():
                set_path(
                    context,
                    path,
                    [
                        *(resolve_path(context, path) or []),
                        resolve_path(context, expression["value_path"]),
                    ],
                )
        if tag == "endEvent":
            scope = owner[current]
            if scope.tag.endswith("subProcess"):
                current = scope
            else:
                return asked, json.loads(state.text)["outcome"], context
        flows = [nodes[e.text] for e in current.findall("bpmn:outgoing", NS)]
        matching = []
        default = current.get("default")
        for f in flows:
            expr = f.find("bpmn:conditionExpression", NS)
            if expr is not None and evaluate(json.loads(expr.text), context):
                matching.append(f)
        assert len(matching) <= 1, "BPMN alternatives are not mutually exclusive"
        chosen = matching[0] if matching else nodes[default] if default else flows[0]
        current = nodes[chosen.get("targetRef")]
    raise AssertionError("BPMN traversal did not terminate")


@pytest.mark.parametrize("fid", [6, 5871, 7530, 265080])
@pytest.mark.parametrize("mode", ["flat", "auto"])
def test_source_metadata_questions_di_and_determinism(fid, mode):
    export = source(fid)
    untouched = copy.deepcopy(export)
    result = convert_form(export, mode=mode, question_file=f"{fid}.questions.json")
    counts = validate_bpmn(result.xml, result.questions)
    assert counts["nodes"] == counts["shapes"]
    assert counts["flows"] == counts["edges"]
    assert result.questions["source_export"] == export == untouched
    originals = {
        v["source_step_id"]
        for v in result.questions["questions"].values()
        if not v["generated"]
    }
    assert originals == {q["id"] for q in export["content"]["steps"]}
    assert (
        result.xml
        == convert_form(export, mode=mode, question_file=f"{fid}.questions.json").xml
    )
    compiled = compile_form(export)["processes"]["main"]["states"]
    root = ET.fromstring(result.xml)
    for task in root.findall(".//bpmn:userTask", NS):
        ref = task.find("bpmn:extensionElements/forms:stateRef", NS)
        assert (
            result.questions["questions"][task.get("id")]["schema"]
            == compiled[ref.get("stateId")]["schema"]
        )


@pytest.mark.parametrize("fid", [6, 5871])
@pytest.mark.parametrize("mode", ["flat", "auto"])
def test_linear_forms_stay_flat_and_follow_links(fid, mode):
    export = source(fid)
    result = convert_form(export, mode=mode)
    assert result.report["decomposition"] == []
    asked, outcome, _ = walk_xml(result, {})
    assert asked == [q["id"] for q in export["content"]["steps"]]
    assert outcome == "form_answers_collected"


@pytest.mark.parametrize("mode", ["flat", "auto"])
@pytest.mark.parametrize(
    "trainer,logo,expected",
    [
        (
            "Approved driving instructor (ADI)",
            None,
            ["B85c9coV", "e2vkqYBz", "rPcxn8SY", "zt6YRs91", "KZQmxcge", "EkmQwcxR"],
        ),
        (
            "Motorcycle trainer",
            "Driver and Vehicle Standards Agency (DVSA) enhanced rider scheme trainer",
            ["B85c9coV", "e2vkqYBz", "rPcxn8SY", "CNMZF7Ne", "NE2jzdq8", "EkmQwcxR"],
        ),
        (
            "Motorcycle trainer",
            "other",
            ["B85c9coV", "e2vkqYBz", "rPcxn8SY", "CNMZF7Ne", "uo2fs5R1", "EkmQwcxR"],
        ),
    ],
)
def test_dvsa_actual_routes(mode, trainer, logo, expected):
    result = convert_form(source(7530), mode=mode)
    asked, outcome, _ = walk_xml(result, {"rPcxn8SY": trainer, "CNMZF7Ne": logo})
    assert asked == expected
    assert outcome == "form_answers_collected"


@pytest.mark.parametrize("mode", ["flat", "auto"])
@pytest.mark.parametrize("visible,branch", [(True, "xa9aPKTh"), (False, "mnjL9UmK")])
def test_ip_actual_routes_and_repetition(mode, visible, branch):
    result = convert_form(source(265080), mode=mode)
    asked, outcome, ctx = walk_xml(
        result, {"59kGCS2D": visible, "M5dD7tjq": "GB123", "__more__": [True, False]}
    )
    assert asked == [
        "Li3wC4fD",
        "Dm1cKMyX",
        "59kGCS2D",
        branch,
        "M5dD7tjq",
        "M5dD7tjq",
        "SXJuBxp1",
        "zCy3HHnq",
    ]
    assert ctx["answers"]["M5dD7tjq"] == ["GB123", "GB123"]
    assert outcome == "form_answers_collected"


def test_inferred_groups_are_based_on_flow_not_headings():
    dvsa = convert_form(source(7530), mode="auto").report["decomposition"]
    assert len(dvsa) == 1
    assert dvsa[0]["question_ids"] == [
        "rPcxn8SY",
        "zt6YRs91",
        "KZQmxcge",
        "CNMZF7Ne",
        "uo2fs5R1",
        "NE2jzdq8",
    ]
    ip = convert_form(source(265080), mode="auto").report["decomposition"]
    assert len(ip) == 2
    assert ip[0]["reason"] == "explicit is_repeatable"
    export = source(5871)
    for q in export["content"]["steps"]:
        q["data"]["page_heading"] = "A new section"
    assert not convert_form(export, mode="auto").report["decomposition"]


def synthetic():
    """Clearly synthetic form: overlapping checkbox routes and a genuine exit."""

    def q(sid, kind, next_id, settings=None):
        return {
            "id": sid,
            "type": "question",
            "position": int(sid[1:]),
            "next_step_id": next_id,
            "routing_conditions": [],
            "data": {
                "question_text": sid + " synthetic question",
                "answer_type": kind,
                "answer_settings": settings,
                "is_optional": False,
                "is_repeatable": False,
            },
        }

    return {
        "form_id": 990001,
        "content": {
            "form_id": 990001,
            "name": "SYNTHETIC — overlapping rules and early exit",
            "start_page": "q1",
            "steps": [
                q(
                    "q1",
                    "selection",
                    "q2",
                    {
                        "only_one_option": False,
                        "selection_options": [
                            {"name": "A", "value": "A"},
                            {"name": "B", "value": "B"},
                        ],
                    },
                ),
                q("q2", "text", None),
            ],
        },
    }


def test_checkbox_rules_keep_first_match_and_early_exit():
    export = synthetic()
    q = export["content"]["steps"][0]
    q["routing_conditions"] = [
        {"answer_value": "A", "goto_page_id": "q2"},
        {
            "answer_value": "B",
            "exit_page_heading": "Cannot continue",
            "exit_page_markdown": "Synthetic exit.",
        },
    ]
    for mode in ["flat", "auto"]:
        result = convert_form(export, mode=mode)
        validate_bpmn(result.xml, result.questions)
        asked, outcome, _ = walk_xml(result, {"q1": ["A", "B"]})
        assert asked == ["q1", "q2"] and outcome == "form_answers_collected"
        asked, outcome, _ = walk_xml(result, {"q1": ["B"]})
        assert asked == ["q1"] and outcome == "exit_page"
        asked, outcome, _ = walk_xml(result, {"q1": []})
        assert asked == ["q1", "q2"] and outcome == "form_answers_collected"
        assert not result.report["decomposition"], "escaping exit must not be wrapped"


@pytest.mark.parametrize(
    "change",
    [
        "missing_target",
        "invalid_selection",
        "unknown_type",
        "payment",
        "bad_exit",
        "future_check",
        "wrong_page",
    ],
)
def test_unsupported_features_fail_loudly(change):
    export = source(7530)
    q = export["content"]["steps"][2]
    if change == "missing_target":
        q["routing_conditions"][0]["goto_page_id"] = "absent"
    elif change == "invalid_selection":
        q["data"]["answer_settings"]["only_one_option"] = None
    elif change == "unknown_type":
        q["data"]["answer_type"] = "new_compound_widget"
    elif change == "payment":
        export["content"]["payment_url"] = "https://payment.invalid"
    elif change == "bad_exit":
        q["exit_pages"] = [{"id": 123, "heading": "Unused"}]
    elif change == "future_check":
        q["routing_conditions"][0]["check_page_id"] = "EkmQwcxR"
    elif change == "wrong_page":
        q["routing_conditions"][0]["routing_page_id"] = "EkmQwcxR"
    with pytest.raises(UnsupportedForm):
        convert_form(export, mode="auto")


def test_optional_repeat_skip_and_checked_earlier_question():
    export = source(265080)
    export["content"]["steps"][5]["data"]["is_optional"] = True
    for mode in ["flat", "auto"]:
        result = convert_form(export, mode=mode)
        asked, _, ctx = walk_xml(result, {"59kGCS2D": False, "M5dD7tjq": ""})
        assert asked == [
            "Li3wC4fD",
            "Dm1cKMyX",
            "59kGCS2D",
            "mnjL9UmK",
            "M5dD7tjq",
            "SXJuBxp1",
            "zCy3HHnq",
        ]
        assert not ctx["answers"].get("M5dD7tjq")
    export = source(7530)
    # Routed at Q9, but consults an earlier required single selection Q3.
    export["content"]["steps"][-1]["routing_conditions"] = [
        {
            "check_page_id": "rPcxn8SY",
            "answer_value": "Motorcycle trainer",
            "exit_page_heading": "Synthetic motorcycle exit",
        }
    ]
    result = convert_form(export)
    asked, outcome, _ = walk_xml(
        result, {"rPcxn8SY": "Motorcycle trainer", "CNMZF7Ne": "other"}
    )
    assert asked[-1] == "EkmQwcxR" and outcome == "exit_page"


def test_xml_ids_are_valid_and_injective():
    import re

    ids = [xml_id("state", x) for x in ["1", "a/b", "a_2f_b", "a b", "a.b", "名字"]]
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch("[A-Za-z_][A-Za-z_0-9]*", x) for x in ids)


def test_validator_rejects_bad_scope_coordinates_and_reference():
    result = convert_form(source(7530), mode="auto")
    for mutation in ["scope", "coordinate", "reference"]:
        root = ET.fromstring(result.xml)
        if mutation == "scope":
            root.find(".//bpmn:sequenceFlow", NS).set("targetRef", "not_a_node")
        elif mutation == "coordinate":
            root.find(".//dc:Bounds", NS).set("width", "-1")
        else:
            root.find(".//forms:questionRef", NS).set("href", "x#/questions/missing")
        with pytest.raises(ValueError):
            validate_bpmn(ET.tostring(root, encoding="unicode"), result.questions)


def test_cli_writes_all_linked_artifacts(tmp_path):
    output = tmp_path / "demo.bpmn"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "forms_bpmn",
            "--input",
            str(FIXTURES / "7530.json"),
            "--output",
            str(output),
            "--mode",
            "auto",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    metadata = json.loads(output.with_suffix(".questions.json").read_text())
    validate_bpmn(output.read_text(), metadata)
    assert output.with_suffix(".svg").read_text().startswith("<svg")
    assert output.with_suffix(".report.json").is_file()
    assert "demo.questions.json#/questions/" in output.read_text()


@pytest.mark.parametrize("fid", [6, 5871, 7530, 265080])
@pytest.mark.parametrize("mode", ["flat", "auto"])
def test_edges_do_not_pass_through_unrelated_shapes(fid, mode):
    def check(graph):
        for edge in graph.edges:
            for node in graph.nodes.values():
                if node.id in {edge.source, edge.target}:
                    continue
                for (x1, y1), (x2, y2) in zip(edge.points, edge.points[1:]):
                    vertical = (
                        x1 == x2
                        and node.x < x1 < node.x + node.width
                        and min(y1, y2) < node.y + node.height
                        and max(y1, y2) > node.y
                    )
                    horizontal = (
                        y1 == y2
                        and node.y < y1 < node.y + node.height
                        and min(x1, x2) < node.x + node.width
                        and max(x1, x2) > node.x
                    )
                    assert not (vertical or horizontal), (edge.id, node.id)
        for node in graph.nodes.values():
            if node.children:
                check(node.children)

    check(convert_form(source(fid), mode=mode).graph)


def test_form_with_only_early_exit_has_no_spurious_normal_end():
    export = synthetic()
    export["content"]["steps"] = export["content"]["steps"][:1]
    q = export["content"]["steps"][0]
    q["next_step_id"] = None
    q["routing_conditions"] = [
        {"answer_value": None, "exit_page_heading": "Synthetic unconditional exit"}
    ]
    for mode in ["flat", "auto"]:
        result = convert_form(export, mode=mode)
        validate_bpmn(result.xml, result.questions)
        assert 'name="Answers collected"' not in result.xml
        asked, outcome, _ = walk_xml(result, {"q1": ["B"]})
        assert asked == ["q1"] and outcome == "exit_page"


def test_skip_to_end_and_referenced_exit_page():
    export = synthetic()
    q = export["content"]["steps"][0]
    q["exit_pages"] = [
        {"id": 42, "heading": "Synthetic stop", "markdown": "Further guidance"}
    ]
    q["routing_conditions"] = [
        {"answer_value": "A", "skip_to_end": True},
        {"answer_value": "B", "exit_page_id": 42},
    ]
    result = convert_form(export)
    assert walk_xml(result, {"q1": ["A"]})[:2] == (["q1"], "form_answers_collected")
    assert walk_xml(result, {"q1": ["B"]})[:2] == (["q1"], "exit_page")
    assert "Further guidance" in result.xml


def test_dvsa_skip_departure_does_not_look_like_entry_to_motorcycle_question():
    result = convert_form(source(7530), mode="auto")
    region = next(n.children for n in result.graph.nodes.values() if n.children)
    task = next(n for n in region.nodes.values() if n.state_id == "KZQmxcge")
    edge = next(e for e in region.edges if e.source == task.id)
    assert edge.points[0][0] != task.x + task.width / 2
