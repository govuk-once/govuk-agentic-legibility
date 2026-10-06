"""
BPMN process discovery.

Builds a registry of process ids to BPMN files.
Used to resolve CallActivity targets.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

BPMN_NS = {
    "bpmn":
        "http://www.omg.org/spec/BPMN/20100524/MODEL",
}


class ProcessRegistry:

    def __init__(
        self,
        process_directory: Path,
    ):
        self.process_directory = process_directory

        self.process_files: dict[
            str,
            Path,
        ] = {}

        self._build_registry()

    def _build_registry(
        self,
    ) -> None:

        for file in self.process_directory.glob(
            "*.bpmn",
        ):
            root = ET.parse(
                file,
            ).getroot()

            process_el = root.find(
                "bpmn:process",
                BPMN_NS,
            )

            if process_el is None:
                continue

            self.process_files[
                process_el.attrib["id"]
            ] = file

    def get_process_path(
        self,
        process_id: str,
    ) -> Path:

        path = self.process_files.get(
            process_id,
        )

        if path is None:
            raise ValueError(
                f"Unknown process '{process_id}'"
            )

        return path