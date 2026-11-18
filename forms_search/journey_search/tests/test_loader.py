"""Tests for loading the catalogue into DynamoDB, with a fake table."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Self

from conftest import FakeEmbedder

from journey_search.loader import Journey, apply, content_hash, existing_hashes, plan, read_catalogue

MODEL = "eu.cohere.embed-v4:0"
JOURNEYS = [
    Journey("6", "Amend my claim for holiday pay accrued", "Amend a redundancy claim.", "amend-holiday"),
    Journey("3652", "Report a mosquito", "Report a mosquito found in the UK."),
]


class FakeTable:
    def __init__(self, pages: list[list[dict[str, Any]]] | None = None) -> None:
        self.pages = pages or [[]]
        self.scans: list[dict[str, Any]] = []
        self.puts: list[dict[str, Any]] = []
        self.deletes: list[dict[str, Any]] = []

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        self.scans.append(kwargs)
        n = len(self.scans) - 1
        page: dict[str, Any] = {"Items": self.pages[n]}
        if n + 1 < len(self.pages):
            page["LastEvaluatedKey"] = {"workflow_id": f"page-{n}"}
        return page

    def batch_writer(self, **kwargs: Any) -> FakeTable:
        return self

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def put_item(self, Item: dict[str, Any]) -> None:
        self.puts.append(Item)

    def delete_item(self, Key: dict[str, Any]) -> None:
        self.deletes.append(Key)


def test_reads_the_enriched_catalogue(tmp_path):
    path = tmp_path / "catalogue.json"
    path.write_text(
        json.dumps({"workflows": [{"workflow_id": 6, "title": "T", "description": "D", "form_slug": "s"}]})
    )
    assert read_catalogue(path) == [Journey("6", "T", "D", "s")]


def test_first_load_embeds_everything():
    work = plan(JOURNEYS, {}, MODEL)
    assert [j.workflow_id for j in work.to_embed] == ["6", "3652"]
    assert work.to_delete == []


def test_rerun_embeds_only_new_or_changed_journeys_and_deletes_removed_ones():
    existing = {
        "6": content_hash(JOURNEYS[0], MODEL),  # unchanged
        "3652": "stale-hash",  # description changed since last load
        "999": "x",  # no longer in the catalogue
    }
    work = plan(JOURNEYS, existing, MODEL)
    assert [j.workflow_id for j in work.to_embed] == ["3652"]
    assert work.unchanged == 1
    assert work.to_delete == ["999"]


def test_changing_the_embedding_model_re_embeds_everything():
    existing = {j.workflow_id: content_hash(j, MODEL) for j in JOURNEYS}
    assert len(plan(JOURNEYS, existing, "amazon.titan-embed-text-v2:0").to_embed) == 2


def test_existing_hashes_follows_scan_pages():
    table = FakeTable(
        [[{"workflow_id": "6", "content_hash": "a"}], [{"workflow_id": "7", "content_hash": "b"}]]
    )
    assert existing_hashes(table) == {"6": "a", "7": "b"}
    assert table.scans[1]["ExclusiveStartKey"] == {"workflow_id": "page-0"}


def test_items_hold_the_contract_fields_and_a_numeric_vector():
    table, embedder = FakeTable(), FakeEmbedder()
    apply(table, embedder, MODEL, plan(JOURNEYS, {"gone": "x"}, MODEL))

    assert embedder.documents == [j.search_text for j in JOURNEYS]
    item = table.puts[0]
    assert {item["workflow_id"], item["title"], item["description"], item["form_slug"]} == {
        "6",
        "Amend my claim for holiday pay accrued",
        "Amend a redundancy claim.",
        "amend-holiday",
    }
    assert item["embedding"] == [Decimal("0.5")] * 4
    assert item["content_hash"] == content_hash(JOURNEYS[0], MODEL)
    assert "form_slug" not in table.puts[1]
    assert table.deletes == [{"workflow_id": "gone"}]


def test_nothing_to_do_makes_no_embedding_call():
    table, embedder = FakeTable(), FakeEmbedder()
    existing = {j.workflow_id: content_hash(j, MODEL) for j in JOURNEYS}
    apply(table, embedder, MODEL, plan(JOURNEYS, existing, MODEL))
    assert embedder.documents == [] and table.puts == []
