"""Bedrock text embeddings, with an on-disk cache for the catalogue.

Supports Cohere Embed (which embeds queries and documents differently) and
Amazon Titan Text Embeddings V2. Vectors are L2-normalised so a dot product
is cosine similarity.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "eu.cohere.embed-v4:0"
COHERE_BATCH_SIZE = 96

InputType = Literal["document", "query"]


class InvokeModelClient(Protocol):
    def invoke_model(self, **kwargs: Any) -> dict[str, Any]: ...


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


class BedrockEmbedder:
    def __init__(self, model_id: str, client: InvokeModelClient) -> None:
        self.model_id = model_id
        self.client = client
        self.requests = 0

    def _invoke(self, body: dict[str, Any]) -> dict[str, Any]:
        self.requests += 1
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(response["body"].read())

    def embed(self, texts: list[str], input_type: InputType) -> np.ndarray:
        if "cohere" in self.model_id:
            vectors = []
            for start in range(0, len(texts), COHERE_BATCH_SIZE):
                result = self._invoke(
                    {
                        "texts": texts[start : start + COHERE_BATCH_SIZE],
                        "input_type": f"search_{input_type}",
                        "embedding_types": ["float"],
                    }
                )
                vectors.extend(result["embeddings"]["float"])
        elif "titan-embed-text" in self.model_id:
            # Titan takes one text per request and has no query/document distinction.
            vectors = [
                self._invoke({"inputText": text, "normalize": True})["embedding"]
                for text in texts
            ]
        else:
            raise ValueError(f"unsupported embedding model: {self.model_id}")
        return _normalise(np.asarray(vectors, dtype=np.float32))


def make_bedrock_embedder(model_id: str, region: str) -> BedrockEmbedder:
    import boto3
    from botocore.config import Config

    config = Config(retries={"mode": "adaptive", "max_attempts": 8})
    return BedrockEmbedder(
        model_id, boto3.client("bedrock-runtime", region_name=region, config=config)
    )


def cache_path(cache_dir: Path, model_id: str) -> Path:
    return cache_dir / f"{re.sub(r'[^A-Za-z0-9.-]+', '_', model_id)}.npz"


def load_document_embeddings(
    embedder: BedrockEmbedder, ids: list[str], texts: list[str], cache_dir: Path
) -> np.ndarray:
    """Embeddings for each text, reusing cached vectors whose text is unchanged."""
    path = cache_path(cache_dir, embedder.model_id)
    hashes = [text_hash(t) for t in texts]
    cached: dict[tuple[str, str], np.ndarray] = {}
    if path.exists():
        with np.load(path) as data:
            cached = {
                (str(i), str(h)): v
                for i, h, v in zip(data["ids"], data["hashes"], data["vectors"])
            }

    missing = [n for n, key in enumerate(zip(ids, hashes)) if key not in cached]
    if missing:
        logger.info(
            "embedding %d catalogue entries with %s", len(missing), embedder.model_id
        )
        fresh = embedder.embed([texts[n] for n in missing], "document")
        for n, vector in zip(missing, fresh):
            cached[(ids[n], hashes[n])] = vector

    vectors = np.stack([cached[key] for key in zip(ids, hashes)])
    if missing:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, ids=np.array(ids), hashes=np.array(hashes), vectors=vectors)
    return vectors
