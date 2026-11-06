"""Shared fakes. Bedrock and DynamoDB are replaced, so no AWS access is needed."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest

from journey_search.contract import Candidate

DIMENSIONS = 4


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeBedrock:
    """Returns a deterministic vector per text, and records each request body."""

    def __init__(self, dimensions: int = DIMENSIONS) -> None:
        self.dimensions = dimensions
        self.requests: list[dict[str, Any]] = []

    def invoke_model(self, **kwargs: Any) -> dict[str, Any]:
        body = json.loads(kwargs["body"])
        self.requests.append({"modelId": kwargs["modelId"], **body})
        vectors = [[float(len(text) + n) for n in range(self.dimensions)] for text in body["texts"]]
        return {"body": io.BytesIO(json.dumps({"embeddings": {"float": vectors}}).encode())}


class FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.documents: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2, 0.3, 0.4]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents.extend(texts)
        return [[0.5, 0.5, 0.5, 0.5] for _ in texts]


CANDIDATES = [
    Candidate(
        workflow_id="3652", title="Report a mosquito", description="Report a mosquito found in the UK."
    ),
    Candidate(
        workflow_id="265276",
        title="Octopus sighting? Let us know!",
        description="Report an octopus sighting.",
    ),
    Candidate(
        workflow_id="6",
        title="Amend my claim for holiday pay accrued",
        description="Amend a redundancy claim.",
    ),
]


class FakeStore:
    def __init__(self, candidates: list[Candidate] = CANDIDATES, error: Exception | None = None) -> None:
        self.candidates = candidates
        self.error = error
        self.calls: list[tuple[list[float], int]] = []

    def search(self, vector, top_k: int) -> list[Candidate]:
        self.calls.append((list(vector), top_k))
        if self.error:
            raise self.error
        return self.candidates[:top_k]
