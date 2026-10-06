"""
BPMN process registry.

Maps process IDs to BPMN files.

The root process is loaded by load_definition().

Subprocesses are loaded lazily by load_process()
when CallActivities are encountered.
"""

from __future__ import annotations

from pathlib import Path

BPMN_DIR = (
    Path(__file__).resolve().parent.parent
)

PROCESS_REGISTRY: dict[str, str] = {
    #
    # Root process
    #
    "dvla.change_of_address":
        str(
            BPMN_DIR
            / "change_of_address.bpmn"
        ),

    #
    # Subprocesses
    #
    "confirm_intent":
        str(
            BPMN_DIR
            / "confirm_intent.bpmn"
        ),

    "name_change_check":
        str(
            BPMN_DIR
            / "name_change_check.bpmn"
        ),

    "driver_lookup":
        str(
            BPMN_DIR
            / "driver_lookup.bpmn"
        ),

    "photo_update":
        str(
            BPMN_DIR
            / "photo_update.bpmn"
        ),

    "signature_update":
        str(
            BPMN_DIR
            / "signature_update.bpmn"
        ),

    "organ_donation":
        str(
            BPMN_DIR
            / "organ_donation.bpmn"
        ),

    "address_selection":
        str(
            BPMN_DIR
            / "address_selection.bpmn"
        ),

    "address_update":
        str(
            BPMN_DIR
            / "address_update.bpmn"
        ),

    "finalisation":
        str(
            BPMN_DIR
            / "finalisation.bpmn"
        ),
}


def get_process_path(
    process_id: str,
) -> str:
    """
    Resolve a process ID to a BPMN file path.
    """

    try:
        return PROCESS_REGISTRY[
            process_id
        ]

    except KeyError as exc:
        raise ValueError(
            f"Unknown BPMN process '{process_id}'"
        ) from exc


def process_exists(
    process_id: str,
) -> bool:
    return process_id in PROCESS_REGISTRY


def list_processes() -> list[str]:
    return sorted(
        PROCESS_REGISTRY.keys()
    )
