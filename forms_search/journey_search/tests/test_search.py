"""Tests for the search service, the Bedrock embedder and the DynamoDB vector store."""

from __future__ import annotations

from typing import Any

import pytest
from conftest import CANDIDATES, DIMENSIONS, FakeBedrock, FakeEmbedder, FakeStore

from journey_search.contract import MAX_LIMIT, MAX_QUERY_CHARS
from journey_search.embeddings import BATCH_SIZE, BedrockCohereEmbedder
from journey_search.search import JourneySearch
from journey_search.store import DynamoDBVectorStore

# =====================================================================
# Search service
# =====================================================================


def test_search_embeds_the_query_and_returns_candidates():
    embedder, store = FakeEmbedder(), FakeStore()

    result = JourneySearch(embedder, store).search("  report a   mosquito ", 2)

    assert embedder.queries == ["report a mosquito"]
    assert store.calls == [([0.1, 0.2, 0.3, 0.4], 2)]
    assert [c.workflow_id for c in result.candidates] == ["3652", "265276"]


def test_limit_is_clamped_to_the_maximum():
    store = FakeStore()
    JourneySearch(FakeEmbedder(), store).search("claim", 500)
    assert store.calls[0][1] == MAX_LIMIT


@pytest.mark.parametrize("query", ["", "   ", "x" * (MAX_QUERY_CHARS + 1)])
def test_unusable_queries_are_rejected_before_any_aws_call(query):
    embedder = FakeEmbedder()
    with pytest.raises(ValueError):
        JourneySearch(embedder, FakeStore()).search(query)
    assert embedder.queries == []


def test_response_has_exactly_the_contract_fields():
    result = JourneySearch(FakeEmbedder(), FakeStore()).search("mosquito", 1)
    assert result.model_dump() == {
        "candidates": [
            {
                "workflow_id": "3652",
                "title": "Report a mosquito",
                "description": "Report a mosquito found in the UK.",
            }
        ]
    }


# =====================================================================
# Bedrock embedder
# =====================================================================


def test_queries_and_documents_use_different_cohere_input_types():
    bedrock = FakeBedrock()
    embedder = BedrockCohereEmbedder(bedrock, "eu.cohere.embed-v4:0", DIMENSIONS)

    embedder.embed_query("report a mosquito")
    embedder.embed_documents(["Report a mosquito\nReport a mosquito found in the UK."])

    assert [r["input_type"] for r in bedrock.requests] == ["search_query", "search_document"]
    assert bedrock.requests[0]["modelId"] == "eu.cohere.embed-v4:0"


def test_documents_are_embedded_in_batches_of_96():
    bedrock = FakeBedrock()
    vectors = BedrockCohereEmbedder(bedrock, "m", DIMENSIONS).embed_documents(["t"] * (BATCH_SIZE + 4))
    assert [len(r["texts"]) for r in bedrock.requests] == [BATCH_SIZE, 4]
    assert len(vectors) == BATCH_SIZE + 4


def test_wrong_dimensions_are_reported():
    with pytest.raises(ValueError, match="expected 8"):
        BedrockCohereEmbedder(FakeBedrock(dimensions=4), "m", 8).embed_query("x")


# =====================================================================
# DynamoDB vector store
# =====================================================================


class FakeDynamoDB:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def search_vectors(self, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(kwargs)
        return {
            "SearchResults": [
                {
                    "Item": {
                        "workflow_id": {"S": c.workflow_id},
                        "title": {"S": c.title},
                        "description": {"S": c.description},
                    },
                    "Score": 0.1 * n,
                }
                for n, c in enumerate(CANDIDATES[: kwargs["TopK"]])
            ]
        }


def test_search_vectors_request_matches_the_api():
    client = FakeDynamoDB()

    DynamoDBVectorStore(client, "journeys", "description-embedding").search([0.25, -1.5e-3], 2)

    request = client.requests[0]
    assert request["TableName"] == "journeys"
    assert request["IndexName"] == "description-embedding"
    # A plain list of number values, not wrapped in an "L" attribute.
    assert request["SearchVector"] == [{"N": "0.25"}, {"N": "-0.0015"}]
    assert request["TopK"] == 2
    projected = [
        request["ExpressionAttributeNames"][name.strip()]
        for name in request["ProjectionExpression"].split(",")
    ]
    assert projected == ["workflow_id", "title", "description"]


def test_results_keep_their_ranked_order_and_drop_scores():
    results = DynamoDBVectorStore(FakeDynamoDB(), "t", "i").search([0.0], 3)
    assert [c.workflow_id for c in results] == ["3652", "265276", "6"]
    assert not hasattr(results[0], "Score")


def test_no_results_is_an_empty_list():
    class Empty:
        def search_vectors(self, **kwargs):
            return {"SearchResults": []}

    assert DynamoDBVectorStore(Empty(), "t", "i").search([0.0], 5) == []
