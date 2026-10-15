import copy
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from forms_bpmn.converter import NS, xml_id
from sfsm_bpmn.converter import (
    UnsupportedSFSM,
    convert_sfsm,
    guarded,
    section_announcements,
    sid_id,
)
from sfsm_bpmn.validate import validate_bpmn

SOURCE = Path(__file__).resolve().parents[2] / "dwp_ma1_schema.json"


@pytest.fixture(scope="module")
def source():
    return json.loads(SOURCE.read_text())


@pytest.fixture(scope="module")
def result(source):
    return convert_sfsm(source)


def test_full_ma1_processes_and_state_metadata(source, result):
    counts = validate_bpmn(result.xml, result.questions)
    assert counts["processes"] == 6
    root = ET.fromstring(result.xml)
    refs = root.findall(".//sfsm:stateRef", NS)
    assert len(refs) == 152
    assert {(r.get("processId"), r.get("stateId")) for r in refs} == {
        (p, s) for p, v in source["processes"].items() for s in v["states"]
    }
    for p, process in source["processes"].items():
        for s, state in process["states"].items():
            element = root.find(f'.//*[@id="{sid_id(p, s)}"]')
            assert (
                json.loads(
                    (
                        element.find("bpmn:extensionElements/sfsm:state", NS)
                        if element.tag.endswith("callActivity")
                        or element.tag.startswith("{" + NS["bpmn"] + "}")
                        else element.find("sfsm:state", NS)
                    ).text
                )
                == state
            )
    assert result.questions["source_sfsm"] == source
    assert len(result.questions["questions"]) == 45


def test_every_transition_and_catch_is_preserved(source, result):
    for pid, process in source["processes"].items():
        graph = result.graphs[pid]
        folded = section_announcements(pid, process)

        def target_id(sid, pid=pid, folded=folded):
            return sid_id(pid, folded.get(sid, sid))

        for sid, state in process["states"].items():
            nid = sid_id(pid, sid)
            if sid in folded:
                assert nid not in graph.nodes
                continue
            if state["type"] == "choice":
                outgoing = [e for e in graph.edges if e.source == nid]
                assert [e.target for e in outgoing] == [
                    target_id(r["next"]) for r in state["rules"]
                ] + [target_id(state["default"])]
                previous = []
                for edge, rule in zip(outgoing, state["rules"]):
                    assert edge.predicate == guarded(rule["when"], previous)
                    previous.append(rule["when"])
                assert outgoing[-1].default and outgoing[-1].predicate is None
            elif state["type"] == "invoke" and state.get("catch"):
                gateway = next(e.target for e in graph.edges if e.source == nid)
                outgoing = [e for e in graph.edges if e.source == gateway]
                assert [e.target for e in outgoing] == [
                    sid_id(pid, c["next"]) for c in state["catch"]
                ] + [target_id(state["next"])]
                assert [e.predicate["op"] for e in outgoing[:-1]] == [
                    "returned_outcome"
                ] + ["and"] * (len(state["catch"]) - 1)
            elif state["type"] != "end":
                assert [e.target for e in graph.edges if e.source == nid] == [
                    target_id(state["next"])
                ]
            if state["type"] == "call" and state.get("catch"):
                event = next(
                    n
                    for n in graph.nodes.values()
                    if n.kind == "boundaryEvent" and n.state["attached_to"] == nid
                )
                assert [e.target for e in graph.edges if e.source == event.id] == [
                    sid_id(pid, state["catch"][0]["next"])
                ]
                assert not any(e.target == event.id for e in graph.edges)


def test_invocations_reuse_process_and_boundary_errors_are_distinct(result):
    root = ET.fromstring(result.xml)
    calls = root.findall(".//bpmn:callActivity", NS)
    assert len(calls) == 6
    assert (
        sum(
            c.get("calledElement") == xml_id("process", "calculate_deadlines")
            for c in calls
        )
        == 2
    )
    assert len(root.findall(".//bpmn:boundaryEvent", NS)) == 6
    assert len(root.findall(".//bpmn:serviceTask", NS)) == 6
    # Non-success child endpoints are normal returns, not BPMN error throws.
    assert not root.findall(".//bpmn:endEvent/bpmn:errorEventDefinition", NS)
    assert all(
        p.get("isExecutable") == "false" for p in root.findall("bpmn:process", NS)
    )


def test_unreachable_state_is_retained_and_reported(result):
    main = next(p for p in result.report["processes"] if p["id"] == "main")
    assert main["unreachable"] == ["end_exception"]
    assert sid_id("main", "end_exception") in result.graphs["main"].nodes
    assert any("end_exception" in w for w in result.report["warnings"])


def test_deterministic_non_mutating_conversion_and_injective_ids(source, result):
    before = copy.deepcopy(source)
    assert convert_sfsm(source).xml == result.xml
    assert source == before
    assert sid_id("a/b", "c") != sid_id("a", "b/c")


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(schema="unknown"),
        lambda d: d["processes"]["main"]["states"]["confirm_intent"].update(
            type="parallel"
        ),
        lambda d: d["processes"]["main"]["states"]["confirm_intent"].update(
            next="missing"
        ),
        lambda d: d["processes"]["main"]["states"]["invoke_section1_about_you"].update(
            process="missing"
        ),
        lambda d: d["processes"]["main"]["states"]["confirm_intent"].update(
            timeout="PT1H"
        ),
        lambda d: d["processes"]["section1_about_you"]["states"]["lookup_identity_api"][
            "catch"
        ][0].update(on="http_500"),
        lambda d: d["processes"]["main"]["states"]["invoke_section1_about_you"].update(
            process="main"
        ),
    ],
)
def test_unsupported_features_are_explicit(source, change):
    changed = copy.deepcopy(source)
    change(changed)
    with pytest.raises(UnsupportedSFSM):
        convert_sfsm(changed)


def test_validator_rejects_malformed_di_and_called_process(result):
    root = ET.fromstring(result.xml)
    root.find(".//dc:Bounds", NS).set("x", "NaN")
    with pytest.raises(ValueError, match="bounds"):
        validate_bpmn(ET.tostring(root, encoding="unicode"))
    root = ET.fromstring(result.xml)
    root.find(".//bpmn:callActivity", NS).set("calledElement", "missing")
    with pytest.raises(ValueError, match="calledElement"):
        validate_bpmn(ET.tostring(root, encoding="unicode"))


def test_overlapping_choice_conditions_exclude_earlier_rule(source):
    d = copy.deepcopy(source)
    state = d["processes"]["main"]["states"]["branch_intent"]
    state["rules"].append(
        {"when": {"op": "is_true", "path": "confirmed_intent"}, "next": "say_cancelled"}
    )
    r = convert_sfsm(d)
    edges = [
        e for e in r.graphs["main"].edges if e.source == sid_id("main", "branch_intent")
    ]
    assert edges[1].predicate["all"][1]["condition"]["any"] == [
        state["rules"][0]["when"]
    ]


def test_cli_fails_without_replacing_existing_outputs(tmp_path):
    import sys
    from unittest.mock import patch

    from sfsm_bpmn.__main__ import main

    src = tmp_path / "source.json"
    out = tmp_path / "journey.bpmn"
    src.write_text(json.dumps({"schema": "unsupported"}))
    out.write_text("previous output")
    with (
        patch.object(
            sys, "argv", ["sfsm_bpmn", "--input", str(src), "--output", str(out)]
        ),
        pytest.raises(SystemExit),
    ):
        main()
    assert out.read_text() == "previous output"


def test_section_announcements_fold_without_losing_source_or_other_outputs(
    source, result
):
    folded = next(p for p in result.report["processes"] if p["id"] == "main")[
        "folded_announcements"
    ]
    assert len(folded) == 4
    root = ET.fromstring(result.xml)
    for sid, call in folded.items():
        assert sid_id("main", sid) not in result.graphs["main"].nodes
        activity = root.find(f'.//*[@id="{sid_id("main", call)}"]')
        announcement = activity.find("bpmn:extensionElements/sfsm:announcement", NS)
        assert (
            json.loads(announcement.find("sfsm:state", NS).text)
            == source["processes"]["main"]["states"][sid]
        )
    assert sid_id("main", "say_cancelled") in result.graphs["main"].nodes
    expanded = convert_sfsm(source, fold_announcements=False)
    assert sid_id("main", "announce_section1") in expanded.graphs["main"].nodes
    validate_bpmn(expanded.xml, expanded.questions)


def test_shared_or_mismatched_calls_do_not_fold(source):
    changed = copy.deepcopy(source)
    process = changed["processes"]["main"]
    process["states"]["branch_intent"]["default"] = "invoke_section1_about_you"
    assert "announce_section1" not in section_announcements("main", process)
    process["states"]["announce_section2"]["next"] = "invoke_section3_about_work"
    assert "announce_section2" not in section_announcements("main", process)
