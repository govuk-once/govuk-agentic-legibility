"""Load the journey catalogue and its embeddings into DynamoDB.

A separate preparation step: the service never embeds the catalogue itself.
Each item stores a hash of its embedded text and the embedding model, so a
re-run only embeds journeys that are new or changed, and removes journeys
that are no longer in the catalogue.

    JOURNEY_SEARCH_TABLE=<table> uv run journey-search-load --dry-run
    JOURNEY_SEARCH_TABLE=<table> uv run journey-search-load --verify "report a mosquito"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from journey_search.config import Settings
from journey_search.embeddings import BedrockCohereEmbedder, Embedder
from journey_search.search import JourneySearch, aws_clients
from journey_search.store import VECTOR_ATTRIBUTE, DynamoDBVectorStore, to_number

# forms_search/data/catalogue.json, produced by forms_search.enrich.
DEFAULT_CATALOGUE = Path(__file__).resolve().parents[3] / "data" / "catalogue.json"


@dataclass(frozen=True)
class Journey:
    workflow_id: str
    title: str
    description: str
    form_slug: str | None = None

    @property
    def search_text(self) -> str:
        return f"{self.title}\n{self.description}"


def read_catalogue(path: Path) -> list[Journey]:
    workflows = json.loads(path.read_text(encoding="utf-8"))["workflows"]
    return [
        Journey(str(w["workflow_id"]), w["title"], w["description"], w.get("form_slug")) for w in workflows
    ]


def content_hash(journey: Journey, model_id: str) -> str:
    return hashlib.sha256(f"{model_id}\n{journey.search_text}".encode()).hexdigest()


@dataclass
class Plan:
    to_embed: list[Journey]
    unchanged: int
    to_delete: list[str]


def plan(journeys: list[Journey], existing: dict[str, str], model_id: str) -> Plan:
    """``existing`` maps workflow_id to the stored content hash."""
    to_embed = [j for j in journeys if existing.get(j.workflow_id) != content_hash(j, model_id)]
    current = {j.workflow_id for j in journeys}
    return Plan(
        to_embed=to_embed,
        unchanged=len(journeys) - len(to_embed),
        to_delete=sorted(set(existing) - current),
    )


def existing_hashes(table: Any) -> dict[str, str]:
    hashes: dict[str, str] = {}
    kwargs: dict[str, Any] = {"ProjectionExpression": "workflow_id, content_hash"}
    while True:
        page = table.scan(**kwargs)
        for item in page.get("Items", []):
            hashes[item["workflow_id"]] = item.get("content_hash", "")
        if "LastEvaluatedKey" not in page:
            return hashes
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def to_item(journey: Journey, vector: list[float], model_id: str, now: str) -> dict[str, Any]:
    item: dict[str, Any] = {
        "workflow_id": journey.workflow_id,
        "title": journey.title,
        "description": journey.description,
        VECTOR_ATTRIBUTE: [Decimal(to_number(x)) for x in vector],
        "embedding_model": model_id,
        "content_hash": content_hash(journey, model_id),
        "updated_at": now,
    }
    if journey.form_slug:
        item["form_slug"] = journey.form_slug
    return item


def apply(table: Any, embedder: Embedder, model_id: str, work: Plan) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    vectors = embedder.embed_documents([j.search_text for j in work.to_embed]) if work.to_embed else []
    with table.batch_writer(overwrite_by_pkeys=["workflow_id"]) as batch:
        for journey, vector in zip(work.to_embed, vectors, strict=True):
            batch.put_item(Item=to_item(journey, vector, model_id, now))
        for workflow_id in work.to_delete:
            batch.delete_item(Key={"workflow_id": workflow_id})


def verify(search: JourneySearch, query: str, attempts: int = 20, delay: float = 15.0) -> None:
    """Search until the index answers. New vectors take a while to become searchable."""
    from botocore.exceptions import ClientError

    for attempt in range(1, attempts + 1):
        try:
            result = search.search(query, 3)
        except ClientError as exc:  # the index reports ValidationException until it is ready
            print(f"index not ready ({type(exc).__name__}); retry {attempt}/{attempts} in {delay:.0f}s")
            time.sleep(delay)
            continue
        print(f"top candidates for {query!r}:")
        for candidate in result.candidates:
            print(f"  {candidate.workflow_id}: {candidate.title}")
        return
    raise SystemExit("the vector index did not answer; check the table's IndexStatus")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    parser.add_argument(
        "--keep-removed", action="store_true", help="Keep journeys no longer in the catalogue"
    )
    parser.add_argument(
        "--verify", metavar="QUERY", help="After loading, search for QUERY to check the index"
    )
    args = parser.parse_args(argv)

    import boto3

    settings = Settings.from_env()
    journeys = read_catalogue(args.catalogue)
    table = boto3.resource("dynamodb", region_name=settings.region).Table(settings.table_name)
    work = plan(journeys, existing_hashes(table), settings.embedding_model_id)
    if args.keep_removed:
        work.to_delete = []
    print(
        f"{len(journeys)} journeys in {args.catalogue.name}: {len(work.to_embed)} to embed and write, "
        f"{work.unchanged} unchanged, {len(work.to_delete)} to delete"
    )
    if args.dry_run:
        return

    bedrock, dynamodb = aws_clients(settings.region)
    embedder = BedrockCohereEmbedder(bedrock, settings.embedding_model_id, settings.embedding_dimensions)
    apply(table, embedder, settings.embedding_model_id, work)
    print(f"wrote {len(work.to_embed)}, deleted {len(work.to_delete)} in {settings.table_name}")
    if args.verify:
        store = DynamoDBVectorStore(dynamodb, settings.table_name, settings.vector_index_name)
        verify(JourneySearch(embedder, store), args.verify)


if __name__ == "__main__":
    main()
