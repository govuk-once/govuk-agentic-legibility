"""Run sample queries against service journey search and compare methods.

Usage (from the repository root, with AWS credentials for embeddings):

    # One query: top results from each method, side by side
    uv run python -m forms_search.search_cli "I saw an octopus while diving"
    uv run python -m forms_search.search_cli "update my redundancy claim" --limit 15 --expect 6 232

    # Exactly what the orchestrator would receive, and its size
    uv run python -m forms_search.search_cli "report a mosquito" --payload --limit 5
    uv run python -m forms_search.search_cli --tool-spec

    # The labelled sample set: ranks of expected journeys and hits at several K
    uv run python -m forms_search.search_cli --samples --ks 1 3 5 10 15 20

Set --embedding-model (or $FORMS_SEARCH_EMBEDDING_MODEL_ID) to compare models,
e.g. amazon.titan-embed-text-v2:0.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
from pathlib import Path

from forms_search.embeddings import DEFAULT_EMBEDDING_MODEL, make_bedrock_embedder
from forms_search.search import (
    RRF_DEPTH,
    RRF_K,
    DATA_DIR,
    DEFAULT_CATALOGUE,
    METHODS,
    JourneySearch,
    load_catalogue,
)
from forms_search.tool import payload_size, search_payload, search_service_journeys

DEFAULT_SAMPLES = DATA_DIR / "sample_queries.json"
DEFAULT_KS = [1, 3, 5, 10, 15, 20]


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def show_query(
    index: JourneySearch, query: str, limit: int, expect: set[str], methods: list[str]
) -> None:
    print(f"\nQuery: {query}\n")
    for method in methods:
        print(f"── {method} " + "─" * (70 - len(method)))
        hits = index.search(query, limit, method)
        if not hits:
            print("   (no results)")
        for hit in hits:
            mark = "*" if hit.journey.workflow_id in expect else " "
            extra = ""
            if hit.component_ranks:
                extra = (
                    "  ["
                    + ", ".join(
                        f"{m} #{r}" if r else f"{m} -"
                        for m, r in hit.component_ranks.items()
                    )
                    + "]"
                )
            print(
                f"{mark}{hit.rank:>3}. {hit.score:7.4f}  {hit.journey.workflow_id:>6}  "
                f"{_truncate(hit.journey.title, 60)}{extra}"
            )
        print()
    if expect:
        print("Rank of expected journeys (- = not in top results):")
        for method in methods:
            ranks = expected_ranks(index, query, method, expect, max(limit, 100))
            print(
                f"   {method:<10}"
                + "  ".join(f"{wid}: {ranks[wid] or '-'}" for wid in sorted(expect))
            )


def expected_ranks(
    index: JourneySearch, query: str, method: str, expect: set[str], depth: int
) -> dict[str, int | None]:
    ranks: dict[str, int | None] = dict.fromkeys(expect)
    for hit in index.search(query, depth, method):
        if hit.journey.workflow_id in ranks:
            ranks[hit.journey.workflow_id] = hit.rank
    return ranks


def run_samples(
    index: JourneySearch, samples_path: Path, ks: list[int], methods: list[str]
) -> None:
    samples = json.loads(samples_path.read_text(encoding="utf-8"))["queries"]
    depth = max(ks)
    # results[method][query_no] = ranks of expected journeys
    results: dict[str, list[dict[str, int | None]]] = {m: [] for m in methods}

    print(f"Ranks of expected journeys (- = beyond rank {depth})\n")
    print(f"{'category':<17}{'query':<58}" + "".join(f"{m:>16}" for m in methods))
    for sample in samples:
        expect = set(sample["expected"])
        cells = []
        for method in methods:
            ranks = expected_ranks(index, sample["query"], method, expect, depth)
            results[method].append(ranks)
            found = sorted(r for r in ranks.values() if r)
            cell = ",".join(map(str, found)) if found else "-"
            if expect and len(found) < len(expect):
                cell += f" ({len(found)}/{len(expect)})"
            cells.append(cell if expect else "n/a")
        print(
            f"{sample['category']:<17}{_truncate(sample['query'], 56):<58}"
            + "".join(f"{c:>16}" for c in cells)
        )

    labelled = [n for n, s in enumerate(samples) if s["expected"]]
    print(f"\nLabelled queries with at least one expected journey: {len(labelled)}")
    print(
        "Any-hit@K: share of those queries with at least one expected journey in the top K."
    )
    print(
        "All-hit@K: share with every expected journey in the top K (differs only for ambiguous queries).\n"
    )
    header = f"{'':<22}" + "".join(f"{'K=' + str(k):>8}" for k in ks)
    print(header)
    for method in methods:
        for label, needs_all in (("any", False), ("all", True)):
            row = []
            for k in ks:
                hits = 0
                for n in labelled:
                    ranks = results[method][n].values()
                    inside = [r is not None and r <= k for r in ranks]
                    hits += all(inside) if needs_all else any(inside)
                row.append(f"{hits}/{len(labelled)}")
            print(
                f"{method + ' ' + label + '-hit':<22}" + "".join(f"{c:>8}" for c in row)
            )

    unlabelled = [s for s in samples if not s["expected"]]
    if unlabelled:
        print(
            "\nQueries with no correct journey in the catalogue: top 3 hybrid candidates"
        )
        for sample in unlabelled:
            hits = index.search(sample["query"], 3, "hybrid")
            titles = "; ".join(_truncate(h.journey.title, 45) for h in hits)
            print(f"   {_truncate(sample['query'], 50):<52}{titles}")

    print("\nTool payload size (hybrid, compact JSON, mean over sample queries)")
    print(f"{'K':>4}{'chars':>10}{'~tokens':>10}")
    for k in ks:
        sizes = [payload_size(search_payload(s["query"], k, index)) for s in samples]
        print(
            f"{k:>4}{statistics.mean(x['chars'] for x in sizes):>10.0f}"
            f"{statistics.mean(x['approx_tokens'] for x in sizes):>10.0f}"
        )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("query", nargs="?", help="Query to run")
    parser.add_argument(
        "--limit", type=int, default=10, help="Results per method (default 10)"
    )
    parser.add_argument("--method", choices=[*METHODS, "all"], default="all")
    parser.add_argument(
        "--expect", nargs="+", default=[], help="Workflow ids you expect, marked with *"
    )
    parser.add_argument(
        "--payload",
        action="store_true",
        help="Print the tool's JSON payload and its size",
    )
    parser.add_argument(
        "--tool-spec",
        action="store_true",
        help="Print the Strands tool spec and its size",
    )
    parser.add_argument(
        "--samples",
        nargs="?",
        const=DEFAULT_SAMPLES,
        type=Path,
        help="Run a sample query file",
    )
    parser.add_argument(
        "--ks", nargs="+", type=int, default=DEFAULT_KS, help="K values for --samples"
    )
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument(
        "--rrf-k", type=int, default=RRF_K, help=f"RRF constant (default {RRF_K})"
    )
    parser.add_argument(
        "--rrf-depth",
        type=int,
        default=RRF_DEPTH,
        help=f"Ranks per method fed to RRF (default {RRF_DEPTH})",
    )
    parser.add_argument(
        "--exclude-test",
        action="store_true",
        help="Drop journeys whose description marks them as test/demo forms",
    )
    parser.add_argument(
        "--embedding-model",
        default=os.environ.get(
            "FORMS_SEARCH_EMBEDDING_MODEL_ID", DEFAULT_EMBEDDING_MODEL
        ),
    )
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-west-2"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("forms_search").setLevel(logging.INFO)
    args = parse_args(argv)
    if args.tool_spec:
        spec = search_service_journeys.tool_spec
        print(json.dumps(spec, indent=2, ensure_ascii=False))
        size = payload_size(spec)
        print(
            f"\nTool spec: {size['chars']} chars, ~{size['approx_tokens']} tokens (sent on every orchestrator turn)"
        )
        return 0
    if not args.query and not args.samples:
        raise SystemExit("give a query or --samples")

    methods = list(METHODS) if args.method == "all" else [args.method]
    embedder = (
        None
        if methods == ["bm25"] and not args.payload
        else make_bedrock_embedder(args.embedding_model, args.region)
    )
    journeys = load_catalogue(args.catalogue, exclude_test=args.exclude_test)
    index = JourneySearch(
        journeys, embedder, rrf_k=args.rrf_k, rrf_depth=args.rrf_depth
    )
    print(
        f"Catalogue: {len(journeys)} journeys"
        + (" (test journeys excluded)" if args.exclude_test else "")
    )
    if embedder:
        print(f"Embedding model: {embedder.model_id}")

    if args.samples:
        run_samples(index, args.samples, sorted(args.ks), methods)
    elif args.payload:
        payload = search_payload(args.query, args.limit, index)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        size = payload_size(payload)
        print(
            f"\n{len(payload['candidates'])} candidates, {size['chars']} chars, ~{size['approx_tokens']} tokens"
        )
    else:
        show_query(index, args.query, args.limit, set(args.expect), methods)

    if embedder:
        print(f"\nBedrock embedding requests this run: {embedder.requests}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
