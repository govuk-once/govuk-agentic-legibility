"""Text embeddings from Cohere Embed on Amazon Bedrock.

Cohere embeds search queries and the documents they are matched against
differently (``input_type``), so queries and catalogue entries must each use
the right type.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Protocol

InputType = Literal["search_query", "search_document"]

# Cohere Embed accepts at most 96 texts per request.
BATCH_SIZE = 96


class InvokeModelClient(Protocol):
    def invoke_model(self, **kwargs: Any) -> dict[str, Any]: ...


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class BedrockCohereEmbedder:
    def __init__(self, client: InvokeModelClient, model_id: str, dimensions: int) -> None:
        self.client = client
        self.model_id = model_id
        self.dimensions = dimensions

    def _embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(
                    {
                        "texts": texts[start : start + BATCH_SIZE],
                        "input_type": input_type,
                        "embedding_types": ["float"],
                    }
                ),
                contentType="application/json",
                accept="application/json",
            )
            vectors.extend(json.loads(response["body"].read())["embeddings"]["float"])
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"{self.model_id} returned {len(vector)} dimensions, expected {self.dimensions}"
                )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "search_query")[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "search_document")
