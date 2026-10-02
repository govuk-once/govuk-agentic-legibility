"""
Metadata extraction for durable workflow BPMN extensions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

BPMN_NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "meta": "urn:durable-workflow:metadata:v1",
}


def load_bpmn_metadata(
    bpmn_file: str,
) -> dict[str, dict[str, Any]]:
    """
    Load workflow metadata from BPMN extension elements.

    Returns:

    {
        "provide_details": {...},
        "check_photo_validity": {...},
        ...
    }
    """

    root = ET.parse(
        Path(bpmn_file),
    ).getroot()

    metadata: dict[str, dict[str, Any]] = {}

    process = root.find(
        "bpmn:process",
        BPMN_NS,
    )

    if process is None:
        return metadata

    task_types = [
        "userTask",
        "serviceTask",
        "manualTask",
    ]

    for task_type in task_types:

        for task in process.findall(
            f"bpmn:{task_type}",
            BPMN_NS,
        ):

            task_id = task.get("id")

            if not task_id:
                continue

            metadata[task_id] = parse_task_metadata(
                task,
            )

    return metadata


def parse_task_metadata(
    task: ET.Element,
) -> dict[str, Any]:

    extension = task.find(
        "bpmn:extensionElements",
        BPMN_NS,
    )

    if extension is None:
        return {}

    result: dict[str, Any] = {}

    handler = extension.find(
        "meta:taskHandler",
        BPMN_NS,
    )

    if handler is not None:

        result["taskHandler"] = {
            "type": handler.get(
                "type",
            ),
        }

    form = extension.find(
        "meta:form",
        BPMN_NS,
    )

    if form is not None:

        result["form"] = {
            "title": form.get(
                "title",
            ),
            "fields": [],
        }

        for field in form.findall(
            "meta:field",
            BPMN_NS,
        ):

            field_data = dict(
                field.attrib,
            )

            constraints = field.find(
                "meta:fileConstraints",
                BPMN_NS,
            )

            if constraints is not None:

                field_data[
                    "fileConstraints"
                ] = dict(
                    constraints.attrib,
                )

            result["form"]["fields"].append(
                field_data,
            )

    http_service = extension.find(
        "meta:httpService",
        BPMN_NS,
    )

    if http_service is not None:

        service = dict(
            http_service.attrib,
        )

        service["inputs"] = [
            dict(i.attrib)
            for i in http_service.findall(
                "meta:input",
                BPMN_NS,
            )
        ]

        service["outputs"] = [
            dict(o.attrib)
            for o in http_service.findall(
                "meta:output",
                BPMN_NS,
            )
        ]

        retry = http_service.find(
            "meta:retry",
            BPMN_NS,
        )

        if retry is not None:

            service["retry"] = dict(
                retry.attrib,
            )

        timeout = http_service.find(
            "meta:timeout",
            BPMN_NS,
        )

        if timeout is not None:

            service["timeout"] = dict(
                timeout.attrib,
            )

        result["httpService"] = service

    mapping = extension.find(
        "meta:mapping",
        BPMN_NS,
    )

    if mapping is not None:

        result["mapping"] = {
            "outputs": [
                dict(item.attrib)
                for item in mapping.findall(
                    "meta:output",
                    BPMN_NS,
                )
            ]
        }

    manual_review = extension.find(
        "meta:manualReview",
        BPMN_NS,
    )

    if manual_review is not None:

        result["manualReview"] = dict(
            manual_review.attrib,
        )

    return result