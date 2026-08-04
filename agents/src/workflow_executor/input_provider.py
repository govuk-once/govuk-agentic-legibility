"""Input-provider interfaces for service journey interactions."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Protocol, TextIO

from agents.src.workflow_executor.types import JsonObject, ReadOnlyJsonObject


class InputProvider(Protocol):
    """Present an interaction and collect a JSON result from a consumer."""

    def collect(self, interaction: ReadOnlyJsonObject) -> JsonObject:
        """Return data for the supplied interaction."""


class JsonCliInputProvider:
    """Developer CLI that accepts each interaction result as a JSON object.
    Initialise the JSON CLI input provider.

        Args:
            input_function: Callable used to read a line of user input.
            output: Stream used to display interaction content and schema.
    """

    def __init__(
        self,
        *,
        input_function: Callable[[str], str] = input,
        output: TextIO = sys.stdout,
    ) -> None:

        self._input = input_function
        self._output = output

    def collect(self, interaction: ReadOnlyJsonObject) -> JsonObject:
        """Print an interaction and prompt until a JSON object is supplied.

        Args:
            interaction: Interaction content and input schema from the service.

        Returns:
            The parsed JSON object entered by the user.
        """
        content = interaction.get("content")
        input_schema = interaction.get("input_schema")

        self._write_section("Interaction", content)
        self._write_section("Expected result schema", input_schema)

        while True:
            raw_value = self._input("Enter result as JSON: ")
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                self._output.write(f"Invalid JSON: {exc.msg}\n")
                continue
            if not isinstance(value, dict):
                self._output.write("The interaction result must be a JSON object.\n")
                continue
            return value

    def _write_section(self, heading: str, value: object) -> None:
        self._output.write(f"\n{heading}:\n")
        if value is None:
            self._output.write("null\n")
            return
        self._output.write(json.dumps(value, indent=2, ensure_ascii=False))
        self._output.write("\n")
