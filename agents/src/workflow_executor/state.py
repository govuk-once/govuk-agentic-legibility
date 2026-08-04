"""Local persistence helpers for suspending and resuming journey execution."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

from agents.src.workflow_executor.errors import JourneyProtocolError
from agents.src.workflow_executor.types import JsonObject


def save_response(response: Mapping[str, object], path: str | Path) -> None:
    """Atomically save the latest complete journey response to a JSON file.

    Args:
        response: Complete response returned by the journey service.
        path: Destination file used to resume execution later.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        text=True,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(dict(response), temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
        Path(temporary_name).replace(destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def load_response(path: str | Path) -> JsonObject:
    """Load a previously saved journey response.

    Args:
        path: JSON file created by `save_response`.

    Returns:
        The saved journey response.

    Raises:
        JourneyProtocolError: If the file does not contain a JSON object.
    """
    with Path(path).open(encoding="utf-8") as response_file:
        response = json.load(response_file)
    if not isinstance(response, dict):
        msg = "Saved journey response must be a JSON object"
        raise JourneyProtocolError(msg)
    return response
