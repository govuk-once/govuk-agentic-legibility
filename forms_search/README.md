# Forms search

Prototype discovery of GOV.UK service journeys for the orchestrating agent:

1. **Enrichment** (`enrich.py`) — generates a short description for each
   GOV.UK Form in `forms_export/` with Claude on Amazon Bedrock, producing
   `data/catalogue.json`.
2. **Search** (`search.py`, `tool.py`) — BM25, Bedrock embedding and hybrid
   (Reciprocal Rank Fusion) retrieval over journey titles and descriptions,
   exposed as the Strands tool `search_service_journeys(query, limit=5)`.
3. **Experiments** (`search_cli.py`) — run queries, compare methods and K
   values, and inspect exactly what the orchestrator receives.

All commands run from the repository root and need AWS credentials for
Bedrock, e.g. by prefixing `gds-cli aws <profile> --`.

## Search tool

```python
from strands import Agent
from forms_search.tool import search_service_journeys

agent = Agent(model=..., tools=[search_service_journeys])
```

The tool is stateless. Each call is one search and returns ranked candidates
only. Scores are not returned and are not probabilities. Searching never
starts a journey.

```json
{
  "query": "change my redundancy claim, I wasn't paid for holiday I took",
  "candidates": [
    {"workflow_id": "232", "title": "Amend my claim for holiday taken but not paid", "description": "…"},
    {"workflow_id": "6", "title": "Amend my claim for holiday pay accrued", "description": "…"}
  ]
}
```

`limit` defaults to 5 and is clamped to 1–20. The tool description (the
docstring of `search_service_journeys`) is part of the contract: it tells the
orchestrator the catalogue includes niche services, that results are only
candidates, and that it is not for information questions.

Settings, all from the environment:

| Variable | Default | Purpose |
|---|---|---|
| `FORMS_SEARCH_METHOD` | `hybrid` | `hybrid`, `embedding` or `bm25` behind the tool |
| `FORMS_SEARCH_EMBEDDING_MODEL_ID` | `eu.cohere.embed-v4:0` | Also supports `amazon.titan-embed-text-v2:0` |
| `AWS_REGION` | `eu-west-2` | |

Catalogue embeddings are cached in `data/embeddings/` (gitignored) and
rebuilt on first use, or for any entry whose text has changed (7 requests for
the full catalogue with Cohere). After that, a query costs one embedding
request.

## Experimenting

```bash
# One query: each method's top results; hybrid shows each method's rank
uv run python -m forms_search.search_cli "I saw an octopus while diving"
uv run python -m forms_search.search_cli "update my redundancy claim" --limit 15 --expect 6 232

# The exact tool payload and its size, and the tool spec's size
uv run python -m forms_search.search_cli "report a mosquito" --payload --limit 5
uv run python -m forms_search.search_cli --tool-spec

# Hand-labelled sample set: ranks of expected journeys, hits at each K,
# top candidates for queries with no right answer, and payload size per K
uv run python -m forms_search.search_cli --samples --ks 1 3 5 10 15 20
```

Other options: `--method`, `--embedding-model`, `--rrf-k` (default 60),
`--rrf-depth` (default 20) and `--exclude-test`, which drops journeys whose
description marks them as test or demo forms.

`data/sample_queries.json` has 27 queries in seven categories: named
services, paraphrases, ambiguous requests, unusual services, a misleading
title, services not in the catalogue, and information questions. It is a
smoke test for comparing settings, not a benchmark. Add queries to it as you
find interesting cases.

## Enrichment

```bash
uv run python -m forms_search.enrich --dry-run --ids 6          # print the prompt only
uv run python -m forms_search.enrich --ids 6 232                # a few Forms
uv run python -m forms_search.enrich --concurrency 8            # everything; resumes
```

Options: `--concurrency` (default 4), `--max-retries` (default 6, exponential
backoff with jitter on throttling, transient errors and unusable output),
`--limit N`, `--force`, `--effort low|medium|high|none`, `--model-id`
(default `eu.anthropic.claude-sonnet-5-5`, or `$FORMS_ENRICH_MODEL_ID`) and
`--region`.

- `form_text.py` renders each export as compact text: title, questions in
  order with hints, options, guidance and exit pages, declaration and "what
  happens next". Very long fields are capped at 1,500 characters.
- Titles of up to five similar Forms are added to the prompt so the
  description can say what distinguishes this one.
- `data/descriptions.jsonl` is an append-only cache. A Form is regenerated
  only when its content hash, `PROMPT_VERSION` or model changes.
- `data/catalogue.json` is rebuilt at the end of every run.

## Tests

```bash
uv run pytest -vrrP --testdox forms_search/tests
```

No AWS access needed: Bedrock is faked.
