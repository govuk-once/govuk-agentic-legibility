"""Service journey search over the enriched catalogue.

Three retrieval methods over each journey's title and description:

- ``bm25``: lexical match (title tokens counted twice as a light field boost).
- ``embedding``: cosine similarity of Bedrock embeddings. Catalogue vectors are
  cached on disk, so a query costs one embedding request.
- ``hybrid``: Reciprocal Rank Fusion of the two rankings. RRF uses ranks only,
  so the two methods' differently-scaled scores never need comparing.

Scores are kept for debugging. They are not probabilities and are not
returned to the orchestrator.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from forms_search.bm25 import BM25, tokenize
from forms_search.embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    BedrockEmbedder,
    load_document_embeddings,
    make_bedrock_embedder,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CATALOGUE = DATA_DIR / "catalogue.json"
DEFAULT_EMBEDDING_CACHE = DATA_DIR / "embeddings"

# Standard RRF constant: dampens the advantage of being ranked first by one
# method, so journeys that both methods rank fairly well rise to the top.
RRF_K = 60
# How far down each method's ranking RRF looks. Kept shallow: with deep lists,
# journeys both methods rank mediocrely outscore one that a single method ranks
# first, which buried good embedding matches under BM25 noise in the sample set.
RRF_DEPTH = 20

# Descriptions written at enrichment time usually say when a Form is a test,
# demo or placeholder. A heuristic only: it also catches some whimsical
# demo-style journeys (e.g. the juggling licence), so it is off by default.
TEST_JOURNEY_PATTERN = re.compile(
    r"\btest (form|version)\b|\bnot (a )?real (service|application|use|submission)"
    r"|\bnot for (real|public|live)\b|\bcapybara\b|\bautomated test"
    r"|\btest or (example|internal)\b|\b(placeholder|example) form\b|\bdemo or test\b",
    re.IGNORECASE,
)

Method = Literal["bm25", "embedding", "hybrid"]
METHODS: tuple[Method, ...] = ("bm25", "embedding", "hybrid")


@dataclass(frozen=True)
class Journey:
    workflow_id: str
    title: str
    description: str

    @property
    def search_text(self) -> str:
        return f"{self.title}\n{self.description}"


@dataclass
class Hit:
    journey: Journey
    rank: int
    score: float
    # Rank in each underlying method, for hybrid results (None if not retrieved).
    component_ranks: dict[str, int | None] = field(default_factory=dict)


def looks_like_test_journey(journey: Journey) -> bool:
    return bool(TEST_JOURNEY_PATTERN.search(journey.description))


def load_catalogue(
    path: Path = DEFAULT_CATALOGUE, exclude_test: bool = False
) -> list[Journey]:
    workflows = json.loads(path.read_text(encoding="utf-8"))["workflows"]
    journeys = [
        Journey(w["workflow_id"], w["title"], w["description"]) for w in workflows
    ]
    if exclude_test:
        journeys = [j for j in journeys if not looks_like_test_journey(j)]
    return journeys


class JourneySearch:
    def __init__(
        self,
        journeys: list[Journey],
        embedder: BedrockEmbedder | None = None,
        embedding_cache: Path = DEFAULT_EMBEDDING_CACHE,
        rrf_k: int = RRF_K,
        rrf_depth: int = RRF_DEPTH,
    ) -> None:
        self.journeys = journeys
        self.embedder = embedder
        self.rrf_k = rrf_k
        self.rrf_depth = rrf_depth
        self._bm25 = BM25(
            [tokenize(f"{j.title} {j.title} {j.description}") for j in journeys]
        )
        self._vectors: np.ndarray | None = None
        self._embedding_cache = embedding_cache
        self._query_vectors: dict[str, np.ndarray] = {}

    @classmethod
    def from_environment(cls, catalogue: Path = DEFAULT_CATALOGUE) -> JourneySearch:
        """Build an index using Bedrock settings from the environment."""
        embedder = make_bedrock_embedder(
            os.environ.get("FORMS_SEARCH_EMBEDDING_MODEL_ID", DEFAULT_EMBEDDING_MODEL),
            os.environ.get("AWS_REGION", "eu-west-2"),
        )
        return cls(load_catalogue(catalogue), embedder)

    # --- individual methods -------------------------------------------------

    def bm25(self, query: str, limit: int) -> list[Hit]:
        scores = self._bm25.scores(tokenize(query))
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [
            Hit(self.journeys[index], rank, score)
            for rank, (index, score) in enumerate(ordered[:limit], start=1)
        ]

    def embedding(self, query: str, limit: int) -> list[Hit]:
        similarities = self._document_vectors() @ self._query_vector(query)
        order = np.argsort(-similarities, kind="stable")[:limit]
        return [
            Hit(self.journeys[index], rank, float(similarities[index]))
            for rank, index in enumerate(order, start=1)
        ]

    def hybrid(self, query: str, limit: int) -> list[Hit]:
        k, depth = self.rrf_k, self.rrf_depth
        rankings = {
            "bm25": self.bm25(query, depth),
            "embedding": self.embedding(query, depth),
        }
        fused: dict[str, float] = {}
        ranks: dict[str, dict[str, int | None]] = {}
        by_id = {}
        for method, hits in rankings.items():
            for hit in hits:
                wid = hit.journey.workflow_id
                by_id[wid] = hit.journey
                fused[wid] = fused.get(wid, 0.0) + 1 / (k + hit.rank)
                ranks.setdefault(wid, dict.fromkeys(rankings))[method] = hit.rank

        def best_rank(wid: str) -> int:
            return min(r for r in ranks[wid].values() if r is not None)

        ordered = sorted(fused, key=lambda wid: (-fused[wid], best_rank(wid), wid))
        return [
            Hit(by_id[wid], rank, fused[wid], ranks[wid])
            for rank, wid in enumerate(ordered[:limit], start=1)
        ]

    def search(
        self, query: str, limit: int = 5, method: Method = "hybrid"
    ) -> list[Hit]:
        if method == "bm25":
            return self.bm25(query, limit)
        if method == "embedding":
            return self.embedding(query, limit)
        if method == "hybrid":
            return self.hybrid(query, limit)
        raise ValueError(f"unknown method: {method}")

    # --- embeddings ---------------------------------------------------------

    def _require_embedder(self) -> BedrockEmbedder:
        if self.embedder is None:
            raise RuntimeError("embedding search needs a Bedrock embedder")
        return self.embedder

    def _document_vectors(self) -> np.ndarray:
        if self._vectors is None:
            self._vectors = load_document_embeddings(
                self._require_embedder(),
                [j.workflow_id for j in self.journeys],
                [j.search_text for j in self.journeys],
                self._embedding_cache,
            )
        return self._vectors

    def _query_vector(self, query: str) -> np.ndarray:
        # Memoised so comparing methods on one query costs a single request.
        if query not in self._query_vectors:
            self._query_vectors[query] = self._require_embedder().embed(
                [query], "query"
            )[0]
        return self._query_vectors[query]
