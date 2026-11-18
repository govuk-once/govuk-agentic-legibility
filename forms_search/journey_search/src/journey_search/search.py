"""Journey search: embed the query, then retrieve the nearest journeys.

This is the seam between the MCP contract and the retrieval implementation.
Swapping the embedder or store changes how candidates are found, not what the
orchestrator sees.
"""

from __future__ import annotations

from journey_search.config import Settings
from journey_search.contract import (
    DEFAULT_LIMIT,
    SearchResponse,
    clamp_limit,
    normalise_query,
)
from journey_search.embeddings import BedrockCohereEmbedder, Embedder
from journey_search.store import DynamoDBVectorStore, VectorStore


class JourneySearch:
    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self.embedder = embedder
        self.store = store

    def search(self, query: str, limit: int = DEFAULT_LIMIT) -> SearchResponse:
        query = normalise_query(query)
        vector = self.embedder.embed_query(query)
        return SearchResponse(candidates=self.store.search(vector, clamp_limit(limit)))


def aws_clients(region: str):
    """Bedrock and DynamoDB clients with short timeouts, so a slow dependency fails fast."""
    import boto3
    from botocore.config import Config

    config = Config(
        region_name=region,
        connect_timeout=3,
        read_timeout=10,
        retries={"mode": "standard", "max_attempts": 3},
    )
    return boto3.client("bedrock-runtime", config=config), boto3.client("dynamodb", config=config)


def build_search(settings: Settings) -> JourneySearch:
    bedrock, dynamodb = aws_clients(settings.region)
    return JourneySearch(
        BedrockCohereEmbedder(bedrock, settings.embedding_model_id, settings.embedding_dimensions),
        DynamoDBVectorStore(dynamodb, settings.table_name, settings.vector_index_name),
    )
