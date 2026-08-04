"""Typed progressive-disclosure guidance exposed by journey services."""

from __future__ import annotations

from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field


class GuidanceTopic(BaseModel):
    """Compact metadata used to select a relevant guidance document."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class GuidanceDirectory(BaseModel):
    """Versioned directory of guidance available for one journey."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    topics: list[GuidanceTopic]


class GuidanceDocument(GuidanceTopic):
    """One retrieved Markdown document and its content provenance."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    content_type: Literal["text/markdown"]
    content: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GuidanceReference(BaseModel):
    """Application-observed provenance for one retrieved document."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    version: str
    sha256: str

    @classmethod
    def from_document(cls, document: GuidanceDocument) -> Self:
        """Create a reference from an actually retrieved document.

        Args:
            document: Guidance document returned by the journey service.

        Returns:
            Application-owned provenance without the Markdown body.
        """
        return cls(
            id=document.id,
            title=document.title,
            version=document.version,
            sha256=document.sha256,
        )


class GuidanceClientProtocol(Protocol):
    """Bounded guidance operations available to an interaction assistant."""

    def list_guidance(self, journey_id: str) -> GuidanceDirectory:
        """List compact guidance metadata for one journey."""

    def get_guidance(self, journey_id: str, topic_id: str) -> GuidanceDocument:
        """Retrieve one advertised Markdown guidance document."""
