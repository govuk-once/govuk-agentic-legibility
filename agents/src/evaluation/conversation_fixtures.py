"""Load version-controlled conversation fixtures for journey runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.src.interaction_assistant import ConversationMessage
from agents.src.workflow_executor.errors import JourneyConfigurationError

DEFAULT_FIXTURE_DIRECTORY = Path(__file__).with_name("fixtures")


class ConversationFixture(BaseModel):
    """One implementation-neutral conversation scenario."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    journey_id: str = Field(min_length=1)
    conversation: list[ConversationMessage] = Field(min_length=1)
    expected: dict[str, Any] | None = None


class ConversationFixtureSummary(BaseModel):
    """Fixture metadata and transcript exposed to demonstration clients."""

    id: str
    version: str
    title: str
    description: str
    journey_id: str
    conversation: list[ConversationMessage]


@dataclass(frozen=True)
class LoadedConversationFixture:
    """Validated fixture paired with a hash of its exact source file."""

    fixture: ConversationFixture
    sha256: str

    def summary(self) -> ConversationFixtureSummary:
        """Return the client-facing fixture representation.

        Returns:
            Fixture metadata and conversation suitable for an API response.
        """
        return ConversationFixtureSummary(
            id=self.fixture.id,
            version=self.fixture.version,
            title=self.fixture.title,
            description=self.fixture.description,
            journey_id=self.fixture.journey_id,
            conversation=self.fixture.conversation,
        )


class ConversationFixtureRepository:
    """Read conversation fixtures from a version-controlled directory.

    Args:
        directory: Directory containing JSON conversation fixtures.
    """

    def __init__(self, directory: Path = DEFAULT_FIXTURE_DIRECTORY) -> None:
        self._directory = directory

    def list(self) -> list[LoadedConversationFixture]:
        """Return all fixtures ordered by title.

        Returns:
            Validated fixtures ordered by their human-readable title.

        Raises:
            JourneyConfigurationError: If fixture files are invalid or duplicate.
        """
        fixtures: list[LoadedConversationFixture] = []
        seen_ids: set[str] = set()
        for path in sorted(self._directory.glob("*.json")):
            loaded = self._load(path)
            if loaded.fixture.id in seen_ids:
                msg = f"Duplicate conversation fixture ID {loaded.fixture.id!r}"
                raise JourneyConfigurationError(msg)
            seen_ids.add(loaded.fixture.id)
            fixtures.append(loaded)
        return sorted(fixtures, key=lambda item: item.fixture.title.casefold())

    def get(self, fixture_id: str) -> LoadedConversationFixture:
        """Return one fixture by ID.

        Args:
            fixture_id: Stable fixture identifier.

        Returns:
            Validated fixture and exact source-file hash.

        Raises:
            KeyError: If no fixture with that ID exists.
            JourneyConfigurationError: If fixture files are invalid.
        """
        for loaded in self.list():
            if loaded.fixture.id == fixture_id:
                return loaded
        raise KeyError(fixture_id)

    @staticmethod
    def _load(path: Path) -> LoadedConversationFixture:
        raw = path.read_bytes()
        try:
            payload = json.loads(raw)
            fixture = ConversationFixture.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            msg = f"Invalid conversation fixture {path}: {exc}"
            raise JourneyConfigurationError(msg) from exc
        return LoadedConversationFixture(
            fixture=fixture,
            sha256=hashlib.sha256(raw).hexdigest(),
        )
