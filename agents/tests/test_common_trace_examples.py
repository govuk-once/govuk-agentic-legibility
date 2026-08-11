"""Golden-file tests for the committed common trace examples."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.src.common_trace.convert import convert_raw_trace, dump_yaml, load_raw_trace

EXAMPLES_DIRECTORY = Path("agents/examples/common_trace")
EXAMPLE_NAMES = (
    "manual-entry-from-conversation-history",
    "postcode-lookup-from-conversation-history",
    "postcode-question-and-proposal",
)


@pytest.mark.parametrize("example_name", EXAMPLE_NAMES)
def test_common_trace_example_is_up_to_date(example_name: str) -> None:
    """Each committed common trace matches conversion of its frozen raw trace."""
    raw_path = EXAMPLES_DIRECTORY / "raw" / f"{example_name}.jsonl"
    expected_path = (
        EXAMPLES_DIRECTORY / "expected" / f"{example_name}.common.yaml"
    )

    common_trace = convert_raw_trace(
        load_raw_trace(raw_path),
        source_trace=raw_path.name,
    )

    assert dump_yaml(common_trace) == expected_path.read_text(encoding="utf-8")
