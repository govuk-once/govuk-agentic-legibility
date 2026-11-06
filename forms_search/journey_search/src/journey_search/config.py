"""Runtime settings, read from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_REGION = "eu-west-2"
DEFAULT_VECTOR_INDEX = "description-embedding"
DEFAULT_EMBEDDING_MODEL = "eu.cohere.embed-v4:0"
DEFAULT_EMBEDDING_DIMENSIONS = 1536


@dataclass(frozen=True)
class Settings:
    table_name: str
    vector_index_name: str = DEFAULT_VECTOR_INDEX
    embedding_model_id: str = DEFAULT_EMBEDDING_MODEL
    embedding_dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    region: str = DEFAULT_REGION

    @classmethod
    def from_env(cls) -> Settings:
        table_name = os.environ.get("JOURNEY_SEARCH_TABLE")
        if not table_name:
            raise SystemExit("JOURNEY_SEARCH_TABLE must be set to the catalogue's DynamoDB table name")
        return cls(
            table_name=table_name,
            vector_index_name=os.environ.get("JOURNEY_SEARCH_VECTOR_INDEX", DEFAULT_VECTOR_INDEX),
            embedding_model_id=os.environ.get("JOURNEY_SEARCH_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            embedding_dimensions=int(
                os.environ.get("JOURNEY_SEARCH_EMBEDDING_DIMENSIONS", DEFAULT_EMBEDDING_DIMENSIONS)
            ),
            region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or DEFAULT_REGION,
        )
