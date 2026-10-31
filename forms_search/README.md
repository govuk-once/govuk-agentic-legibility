# Forms search: catalogue enrichment

Generates a short description for each GOV.UK Form in `forms_export/`, for use
by the workflow search tool. Descriptions come from Claude on Amazon Bedrock
(Converse API via boto3), grounded only in the Form's own content.

## Run

From the repository root:

```bash
# Inspect the prompt for a Form without calling Bedrock
uv run python -m forms_search.enrich --dry-run --ids 6

# Try a few Forms
gds-cli aws <profile> -- uv run python -m forms_search.enrich --ids 6 232

# Everything (resumes; already-described Forms are skipped)
gds-cli aws <profile> -- uv run python -m forms_search.enrich --concurrency 8
```

Options: `--concurrency` (default 4), `--max-retries` (default 6, exponential
backoff with jitter on throttling/transient errors and on unusable output),
`--limit N`, `--force`, `--effort low|medium|high|none`, `--model-id`
(default `eu.anthropic.claude-sonnet-5-5`, or `$FORMS_ENRICH_MODEL_ID`) and
`--region` (default `$AWS_REGION` or `eu-west-2`).

## Outputs (`forms_search/data/`)

- `descriptions.jsonl` — append-only cache, one record per generation, with
  source hash, prompt version, model, token usage and attempts. A Form is
  regenerated only when its content hash, `PROMPT_VERSION` or model changes.
- `catalogue.json` — rebuilt at the end of every run:

```json
{
  "workflows": [
    {
      "workflow_id": "6",
      "title": "Amend my claim for holiday pay accrued",
      "description": "…",
      "form_slug": "amend-my-claim-for-holiday-pay-accrued",
      "model_id": "eu.anthropic.claude-sonnet-5-5",
      "prompt_version": "1"
    }
  ],
  "missing_descriptions": []
}
```

## How it works

- `form_text.py` renders each export as compact text: title, questions in
  order with hints, options, guidance and exit pages, declaration and "what
  happens next". Very long fields are capped at 1,500 characters.
- Titles of up to five similar Forms (by title word overlap) are added to the
  prompt so the description can say what distinguishes this one.
- Descriptions over 60 words, empty responses and truncated responses are
  retried.

## Tests

```bash
uv run pytest -vrrP --testdox forms_search/tests
```
