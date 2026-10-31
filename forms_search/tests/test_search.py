"""Tests for service journey search and the Strands tool.

Bedrock embeddings are replaced with deterministic fakes — no AWS access required.
"""

from __future__ import annotations

import io
import json
import zlib

import numpy as np
import pytest

from forms_search import tool
from forms_search.bm25 import stem, tokenize
from forms_search.embeddings import BedrockEmbedder, load_document_embeddings
from forms_search.search import Journey, JourneySearch, looks_like_test_journey

JOURNEYS = [
    Journey(
        "6",
        "Amend my claim for holiday pay accrued",
        "Amend an existing redundancy claim for accrued holiday pay.",
    ),
    Journey(
        "232",
        "Amend my claim for holiday taken but not paid",
        "Amend a redundancy claim for unpaid holidays taken.",
    ),
    Journey(
        "265276",
        "Octopus sighting? Let us know!",
        "Report an octopus sighting to the Marine Management Organisation.",
    ),
    Journey("3652", "Report a mosquito", "Report a mosquito found in the UK to UKHSA."),
    Journey(
        "264215",
        "Request for a cooling off period (TM9C)",
        "Request a cooling off period in trade mark opposition.",
    ),
]


class FakeEmbedder:
    """Hashed bag-of-words vectors, plus a synonym so 'cephalopod' means 'octopus'."""

    model_id = "fake-embedder"

    def __init__(self) -> None:
        self.requests = 0

    def embed(self, texts, input_type):
        self.requests += 1
        vectors = np.zeros((len(texts), 64), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in tokenize(text.replace("cephalopod", "octopus")):
                vectors[row, zlib.crc32(token.encode()) % 64] += 1
        return vectors / np.maximum(
            np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9
        )


@pytest.fixture
def index(tmp_path) -> JourneySearch:
    return JourneySearch(
        JOURNEYS, FakeEmbedder(), embedding_cache=tmp_path / "embeddings"
    )


# =====================================================================
# Tokenising and BM25
# =====================================================================


def test_stemming_joins_simple_inflections():
    assert stem("sightings") == stem("sighting") == "sight"
    assert stem("holidays") == "holiday"
    assert stem("business") == "business"


def test_tokenize_drops_stopwords_like_off():
    assert tokenize("I saw an octopus while diving off Cornwall") == [
        "saw",
        "octopus",
        "div",
        "cornwall",
    ]


def test_bm25_ranks_lexical_match_first(index):
    hits = index.bm25("report an octopus sighting", 5)
    assert hits[0].journey.workflow_id == "265276"
    assert [h.rank for h in hits] == list(range(1, len(hits) + 1))


def test_bm25_returns_only_documents_sharing_a_term(index):
    assert index.bm25("zebra crossing", 5) == []


# =====================================================================
# Embeddings and hybrid
# =====================================================================


def test_embedding_finds_semantic_match_bm25_misses(index):
    assert index.bm25("I saw a cephalopod", 5) == []
    assert index.embedding("I saw a cephalopod", 5)[0].journey.workflow_id == "265276"


def test_hybrid_fuses_ranks_and_records_components(index):
    hits = index.hybrid("amend redundancy claim holiday", 5)
    top_two = {h.journey.workflow_id for h in hits[:2]}
    assert top_two == {"6", "232"}
    assert set(hits[0].component_ranks) == {"bm25", "embedding"}
    # RRF score for a journey ranked r1 and r2 is 1/(60+r1) + 1/(60+r2).
    first = hits[0]
    expected = sum(1 / (60 + r) for r in first.component_ranks.values() if r)
    assert first.score == pytest.approx(expected)


def test_hybrid_includes_results_from_only_one_method(index):
    hits = index.hybrid("cephalopod", 5)
    assert hits[0].journey.workflow_id == "265276"
    assert hits[0].component_ranks["bm25"] is None


def test_query_embedding_is_memoised_across_methods(index):
    index.search("report a mosquito", 3, "embedding")
    before = index.embedder.requests
    index.search("report a mosquito", 3, "hybrid")
    assert index.embedder.requests == before


def test_unknown_method_is_rejected(index):
    with pytest.raises(ValueError):
        index.search("x", 3, "softmax")


def test_test_journey_heuristic():
    assert looks_like_test_journey(
        Journey("1", "capybara test form", "Automated test form, not for real use.")
    )
    assert not looks_like_test_journey(JOURNEYS[3])
    assert not looks_like_test_journey(
        Journey(
            "5123",
            "Apply to claim expenses for a cancelled driving test",
            "Claim expenses after DVSA cancelled a test.",
        )
    )


# =====================================================================
# Embedding cache
# =====================================================================


class FakeCohereClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def invoke_model(self, **kwargs):
        body = json.loads(kwargs["body"])
        self.calls.append(body)
        vectors = [[float(len(t)), 1.0, 0.0] for t in body["texts"]]
        return {
            "body": io.BytesIO(json.dumps({"embeddings": {"float": vectors}}).encode())
        }


def test_document_embeddings_are_cached_and_only_changed_text_re_embedded(tmp_path):
    client = FakeCohereClient()
    embedder = BedrockEmbedder("eu.cohere.embed-v4:0", client)

    first = load_document_embeddings(embedder, ["1", "2"], ["alpha", "beta"], tmp_path)
    assert client.calls[0]["input_type"] == "search_document"
    assert np.allclose(np.linalg.norm(first, axis=1), 1)

    load_document_embeddings(embedder, ["1", "2"], ["alpha", "beta"], tmp_path)
    assert len(client.calls) == 1

    load_document_embeddings(embedder, ["1", "2"], ["alpha", "beta changed"], tmp_path)
    assert client.calls[1]["texts"] == ["beta changed"]


def test_query_embedding_uses_search_query_input_type():
    client = FakeCohereClient()
    BedrockEmbedder("eu.cohere.embed-v4:0", client).embed(["octopus"], "query")
    assert client.calls[0]["input_type"] == "search_query"


# =====================================================================
# Tool contract
# =====================================================================


def test_payload_contains_only_candidate_fields(index):
    payload = tool.search_payload("report an octopus", 2, index)
    assert payload["query"] == "report an octopus"
    assert len(payload["candidates"]) == 2
    assert set(payload["candidates"][0]) == {"workflow_id", "title", "description"}
    assert payload["candidates"][0]["workflow_id"] == "265276"


def test_limit_is_clamped(index):
    assert len(tool.search_payload("claim", 0, index)["candidates"]) == 1
    assert len(tool.search_payload("claim", 500, index)["candidates"]) <= tool.MAX_LIMIT


def test_strands_tool_returns_success_result(index):
    tool.set_index(index)
    try:
        result = tool.search_service_journeys("report a mosquito", limit=1)
    finally:
        tool.set_index(None)
    assert result["status"] == "success"
    assert result["content"][0]["json"]["candidates"][0]["workflow_id"] == "3652"


def test_tool_spec_describes_journeys_and_parameters():
    spec = tool.search_service_journeys.tool_spec
    assert spec["name"] == "search_service_journeys"
    assert "octopus" in spec["description"]
    properties = spec["inputSchema"]["json"]["properties"]
    assert set(properties) == {"query", "limit"}
    assert spec["inputSchema"]["json"]["required"] == ["query"]


def test_payload_size_counts_compact_json():
    size = tool.payload_size({"candidates": [{"title": "abcd"}]})
    assert size["chars"] == len('{"candidates":[{"title":"abcd"}]}')
