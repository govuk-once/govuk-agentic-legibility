"""Vector retrieval of journeys from a DynamoDB vector index.

The table holds one item per journey: ``workflow_id`` (partition key),
``title``, ``description`` and the ``embedding`` attribute indexed by a
COSINE vector index. ``SearchVectors`` returns the nearest items, most similar
first. The index projects only the fields the contract returns.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from journey_search.contract import Candidate

VECTOR_ATTRIBUTE = "embedding"
# The index projection (CDK stack) must include these attributes.
RESULT_ATTRIBUTES = ("workflow_id", "title", "description")


class SearchVectorsClient(Protocol):
    def search_vectors(self, **kwargs: Any) -> dict[str, Any]: ...


class VectorStore(Protocol):
    def search(self, vector: Sequence[float], top_k: int) -> list[Candidate]: ...


def to_number(value: float) -> str:
    """A float as a DynamoDB number string. Vectors are indexed at 32-bit precision."""
    return f"{value:.9g}"


class DynamoDBVectorStore:
    def __init__(self, client: SearchVectorsClient, table_name: str, index_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.index_name = index_name

    def search(self, vector: Sequence[float], top_k: int) -> list[Candidate]:
        names = {f"#a{n}": name for n, name in enumerate(RESULT_ATTRIBUTES)}
        response = self.client.search_vectors(
            TableName=self.table_name,
            IndexName=self.index_name,
            # A plain list of numbers, not wrapped in an "L" attribute value.
            SearchVector=[{"N": to_number(x)} for x in vector],
            TopK=top_k,
            ProjectionExpression=", ".join(names),
            ExpressionAttributeNames=names,
        )
        return [
            Candidate(**{name: result["Item"][name]["S"] for name in RESULT_ATTRIBUTES})
            for result in response.get("SearchResults", [])
        ]
