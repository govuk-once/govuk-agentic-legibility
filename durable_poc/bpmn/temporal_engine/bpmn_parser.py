"""
BPMN XML parser.

Converts BPMN XML into BPMNDefinition objects
for execution by the Temporal BPMN interpreter.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

from bpmn.temporal_engine.bpmn_model import (
    BPMNDefinition,
    BPMNProcess,
    BoundaryEvent,
    CallActivity,
    EndEvent,
    ExclusiveGateway,
    ManualTask,
    ParallelGateway,
    SequenceFlow,
    ServiceTask,
    StartEvent,
    UserTask,
    WorkflowExecutorConfig,
    WorkflowMetadata,
    TimerEvent,
)

BPMN_NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
}

META_NS = {
    "meta": "urn:durable-workflow:metadata:v1",
}


def parse_bpmn_file(
    path: str | Path,
) -> BPMNDefinition:

    tree = ET.parse(path)

    root = tree.getroot()

    definition_id = root.attrib.get("id", "workflow")

    processes: dict[str, BPMNProcess] = {}

    for process_el in root.findall(
        "bpmn:process",
        BPMN_NS,
    ):
        process = parse_process(
            process_el,
        )

        processes[process.id] = process

    if not processes:
        raise ValueError("No BPMN process found")

    first_process = next(iter(processes.values()))

    version = "1.0.0"

    if first_process.workflow_metadata:
        version = first_process.workflow_metadata.version

    print(f"Parsed BPMN definition {definition_id}: {len(processes)} process(es)")

    return BPMNDefinition(
        schema="bpmn/0.1",
        id=definition_id,
        version=version,
        entry=first_process.id,
        executor=WorkflowExecutorConfig(),
        processes=processes,
    )


def parse_process(
    process_el: ET.Element,
) -> BPMNProcess:

    process_id = process_el.attrib["id"]

    nodes = {}

    flows = {}

    start_event = None

    workflow_metadata = parse_process_metadata(
        process_el,
    )

    #
    # Start Events
    #

    for el in process_el.findall(
        "bpmn:startEvent",
        BPMN_NS,
    ):
        node = StartEvent(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
        )

        nodes[node.id] = node

        start_event = node.id

    #
    # User Tasks
    #

    for el in process_el.findall(
        "bpmn:userTask",
        BPMN_NS,
    ):
        node = UserTask(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            metadata=parse_extension_elements(
                el,
            ),
        )

        nodes[node.id] = node

    #
    # Service Tasks
    #

    for el in process_el.findall(
        "bpmn:serviceTask",
        BPMN_NS,
    ):
        metadata = parse_extension_elements(
            el,
        )

        node = ServiceTask(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            metadata=metadata,
            implementation=metadata,
        )

        nodes[node.id] = node

    #
    # Manual Tasks
    #

    for el in process_el.findall(
        "bpmn:manualTask",
        BPMN_NS,
    ):
        node = ManualTask(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            metadata=parse_extension_elements(
                el,
            ),
        )

        nodes[node.id] = node

    #
    # Call Activities
    #

    for el in process_el.findall(
        "bpmn:callActivity",
        BPMN_NS,
    ):
        node = CallActivity(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            called_element=el.attrib["calledElement"],
            metadata=parse_extension_elements(
                el,
            ),
        )

        nodes[node.id] = node

    #
    # Exclusive Gateways
    #

    for el in process_el.findall(
        "bpmn:exclusiveGateway",
        BPMN_NS,
    ):
        node = ExclusiveGateway(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
        )

        nodes[node.id] = node

    #
    # Parallel Gateways
    #

    for el in process_el.findall(
        "bpmn:parallelGateway",
        BPMN_NS,
    ):
        node = ParallelGateway(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
        )

        nodes[node.id] = node

    #
    # End Events
    #

    for el in process_el.findall(
        "bpmn:endEvent",
        BPMN_NS,
    ):
        node = EndEvent(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
        )

        nodes[node.id] = node

    #
    # Timer Events
    #

    for el in process_el.findall(
        "bpmn:intermediateCatchEvent",
        BPMN_NS,
    ):
        timer_def = el.find(
            "bpmn:timerEventDefinition",
            BPMN_NS,
        )

        if timer_def is None:
            continue

        duration = timer_def.find(
            "bpmn:timeDuration",
            BPMN_NS,
        )

        if duration is None or not duration.text:
            continue

        node = TimerEvent(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            duration=duration.text.strip(),
        )

        nodes[node.id] = node

    #
    # Boundary Events
    #

    for el in process_el.findall(
        "bpmn:boundaryEvent",
        BPMN_NS,
    ):
        error_ref = None

        err = el.find(
            "bpmn:errorEventDefinition",
            BPMN_NS,
        )

        if err is not None:
            error_ref = err.attrib.get("errorRef")

        node = BoundaryEvent(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            attached_to_ref=el.attrib["attachedToRef"],
            error_ref=error_ref,
        )

        nodes[node.id] = node

    #
    # Sequence Flows
    #

    for el in process_el.findall(
        "bpmn:sequenceFlow",
        BPMN_NS,
    ):
        condition = None

        condition_el = el.find(
            "bpmn:conditionExpression",
            BPMN_NS,
        )

        if condition_el is not None and condition_el.text:
            condition = condition_el.text.strip()

        flow = SequenceFlow(
            id=el.attrib["id"],
            source_ref=el.attrib["sourceRef"],
            target_ref=el.attrib["targetRef"],
            condition=condition,
        )

        flows[flow.id] = flow

    #
    # Default Gateway Routes
    #

    for gateway in process_el.findall(
        "bpmn:exclusiveGateway",
        BPMN_NS,
    ):
        default_flow = gateway.attrib.get("default")

        if default_flow and default_flow in flows:
            flows[default_flow].is_default = True

    if start_event is None:
        raise ValueError(f"Process '{process_id}' contains no start event")

    print(f"Parsed process {process_id}: {len(nodes)} nodes, {len(flows)} flows")

    return BPMNProcess(
        id=process_id,
        start_event=start_event,
        workflow_metadata=workflow_metadata,
        variables={},
        nodes=nodes,
        flows=flows,
    )


def parse_process_metadata(
    process_el: ET.Element,
) -> WorkflowMetadata | None:

    extensions = process_el.find(
        "bpmn:extensionElements",
        BPMN_NS,
    )

    if extensions is None:
        return None

    workflow_meta = extensions.find(
        "meta:workflowMetadata",
        META_NS,
    )

    if workflow_meta is None:
        return None

    return WorkflowMetadata(
        name=workflow_meta.attrib.get(
            "name",
            "",
        ),
        version=workflow_meta.attrib.get(
            "version",
            "1.0.0",
        ),
    )


def parse_extension_elements(
    node_el: ET.Element,
) -> dict:

    metadata: dict = {}

    extensions = node_el.find(
        "bpmn:extensionElements",
        BPMN_NS,
    )

    if extensions is None:
        return metadata

    #
    # taskHandler
    #

    handler = extensions.find(
        "meta:taskHandler",
        META_NS,
    )

    if handler is not None:
        metadata["taskHandler"] = {
            "type": handler.attrib.get(
                "type",
            )
        }

    #
    # form
    #

    form = extensions.find(
        "meta:form",
        META_NS,
    )

    if form is not None:
        metadata["form"] = {
            "title": form.attrib.get(
                "title",
            ),
            "fields": [
                dict(field.attrib)
                for field in form.findall(
                    "meta:field",
                    META_NS,
                )
            ],
        }

    #
    # httpService
    #

    service = extensions.find(
        "meta:httpService",
        META_NS,
    )

    if service is not None:
        metadata["httpService"] = {
            "service": service.attrib.get(
                "service",
                "default",
            ),
            "method": service.attrib.get(
                "method",
            ),
            "endpoint": service.attrib.get(
                "endpoint",
            ),
            "inputs": [
                dict(x.attrib)
                for x in service.findall(
                    "meta:input",
                    META_NS,
                )
            ],
            "outputs": [
                dict(x.attrib)
                for x in service.findall(
                    "meta:output",
                    META_NS,
                )
            ],
        }

        retry = service.find(
            "meta:retry",
            META_NS,
        )

        if retry is not None:
            metadata["httpService"]["retry"] = dict(retry.attrib)

        timeout = service.find(
            "meta:timeout",
            META_NS,
        )

        if timeout is not None:
            metadata["httpService"]["timeout"] = dict(timeout.attrib)

    #
    # mapping
    #

    mapping = extensions.find(
        "meta:mapping",
        META_NS,
    )

    if mapping is not None:
        metadata["mapping"] = {
            "outputs": [
                dict(x.attrib)
                for x in mapping.findall(
                    "meta:output",
                    META_NS,
                )
            ]
        }

    #
    # manual review
    #

    review = extensions.find(
        "meta:manualReview",
        META_NS,
    )

    if review is not None:
        metadata["manualReview"] = dict(review.attrib)

    return metadata
