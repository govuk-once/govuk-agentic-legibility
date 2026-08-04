"""Tests for version-controlled conversation fixture loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.src.evaluation import ConversationFixtureRepository
from agents.src.workflow_executor.errors import JourneyConfigurationError


def write_fixture(path: Path, *, fixture_id: str) -> None:
    """Write one minimal valid fixture.

    Args:
        path: Destination JSON path.
        fixture_id: Stable ID written into the fixture.
    """
    path.write_text(
        json.dumps(
            {
                "id": fixture_id,
                "version": "1",
                "title": fixture_id,
                "description": "Test fixture",
                "journey_id": "example-journey",
                "conversation": [
                    {"role": "user", "content": "Use postcode lookup."}
                ],
            }
        ),
        encoding="utf-8",
    )


def test_repository_loads_fixture_and_hashes_exact_source(tmp_path: Path) -> None:
    """Fixtures retain stable metadata and an exact source-file hash."""
    fixture_path = tmp_path / "fixture.json"
    write_fixture(fixture_path, fixture_id="example")

    loaded = ConversationFixtureRepository(tmp_path).get("example")

    assert loaded.fixture.conversation[0].content == "Use postcode lookup."
    assert len(loaded.sha256) == 64
    assert loaded.summary().id == "example"


def test_repository_rejects_duplicate_fixture_ids(tmp_path: Path) -> None:
    """A fixture ID identifies exactly one version-controlled scenario."""
    write_fixture(tmp_path / "one.json", fixture_id="duplicate")
    write_fixture(tmp_path / "two.json", fixture_id="duplicate")

    with pytest.raises(JourneyConfigurationError, match="Duplicate"):
        ConversationFixtureRepository(tmp_path).list()
