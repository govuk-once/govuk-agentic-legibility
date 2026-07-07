# Evaluating deterministic form completion with language models

This repository contains a local evaluation harness for testing whether a language model can complete structured forms consistently and correctly.

Each experiment combines:

* a natural-language case description
* a form represented as a JSON Schema-backed function tool
* a known set of expected tool arguments
* experiment settings such as the model and number of runs

The harness sends the same request to a model repeatedly and measures both correctness and repeatability across independent runs.

The current fixtures range from a simple contact-details baseline to an address-history form containing a repeated array of structured address records. The harness is designed so that further forms can be added as self-contained fixture directories without changing the shared evaluator.

This is not a browser form, frontend, application server or database-backed workflow. The experiments are deliberately controlled, one-shot form-completion tasks. Later fixtures can introduce complications such as ambiguity, corrections, missing information, branching, conversation history, multiple tools or consequential actions.

## Requirements and installation

Use Python 3.12 or later and `uv`.

Install the project and its dependencies:

```bash
uv sync
```

Run the local checks:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

AWS Bedrock credentials are provided through `aws-vault`. Commands that make live model calls must be wrapped with:

```bash
gds-cli <profile> -- <command>
```

API keys and other credentials are not written to result files or logs.

## Fixture structure

Each experiment is defined by a fixture directory:

```text
fixtures/
└── address_history/
    ├── experiment.json
    ├── instructions.txt
    ├── case.txt
    ├── tool_schema.json
    ├── expected_arguments.json
    └── evaluation.json          # optional
```

The fixture directory is passed directly to the CLI. Its `experiment.json` contains the normal run settings, so experiment configuration remains alongside the case, schema and expected result.

For example:

```json
{
  "model": "bedrock/converse/eu.anthropic.claude-haiku-4-5-20251001-v1:0",
  "runs": 1000,
  "concurrency": 5,
  "max_retries": 10,
  "progress": true
}
```

A dated model snapshot is preferable because reproducibility matters: if the underlying model changes, results from experiments run at different times become harder to compare.

Model values are applied in the following order of precedence:

1. command-line option
2. the fixture's `experiment.json`
3. `LITELLM_MODEL`
4. the application's default model

Other command-line options also override the corresponding values in `experiment.json`.

## Inspecting an experiment

Before making live calls, use `dry-run` to inspect the request:

```bash
uv run trivial-form-eval dry-run \
  fixtures/address_history
```

The dry run shows:

* the messages sent to the model
* the tool schema
* the forced tool choice
* the requested model
* the expected arguments

The expected arguments are displayed separately and are not included in the model request. No model call is made, so AWS credentials are not required.

## Running an experiment

Run the experiment using the settings in the fixture's `experiment.json`:

```bash
gds-cli <profile> -- uv run trivial-form-eval run \
  fixtures/address_history
```

Live calls incur provider usage and cost.

Before starting the full configured experiment, run a single-call smoke test by overriding `runs`:

```bash
gds-cli <profile> -- uv run trivial-form-eval run \
  fixtures/address_history \
  --runs 1
```

A small ten-call run can be useful before a large experiment:

```bash
gds-cli <profile> -- uv run trivial-form-eval run \
  fixtures/address_history \
  --runs 10
```

Once the rendered request and initial responses look correct, run the fixture without overrides to use its recorded experiment settings.

Command-line options are intended for smoke tests and temporary variations. Settings for a recorded experiment should normally be committed in the fixture's `experiment.json`.

For example, to test a different model temporarily:

```bash
gds-cli <profile> -- uv run trivial-form-eval run \
  fixtures/address_history \
  --model bedrock/converse/eu.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --runs 10
```

Runs show a terminal progress bar by default. Disable it temporarily with:

```bash
gds-cli <profile> -- uv run trivial-form-eval run \
  fixtures/address_history \
  --no-progress
```

Alternatively, set `"progress": false` in `experiment.json`.

## Stopping an experiment early

To run only part of a larger configured experiment while still writing the normal result and analysis files, use `--stop-after`:

```bash
gds-cli <profile> -- uv run trivial-form-eval run \
  fixtures/address_history \
  --stop-after 200
```

The configured number of requested runs remains part of the experiment definition, but the process stops after the specified number of completed calls.

During a live run, pressing `Ctrl+C` once will:

* stop scheduling further model calls
* retain the responses collected so far
* finalise the result files
* print the available report

The command exits with code 130 unless `--no-fail` is set.

The run manifest records whether the experiment:

* completed normally
* stopped because of `--stop-after`
* stopped because of `Ctrl+C`

Use `--no-finalise-on-interrupt` to restore immediate interrupt behaviour.

## Result files

Each experiment creates a directory under `runs/`. Its contents include:

```text
manifest.json
request.json
expected_arguments.json
evaluation.json
responses.jsonl
summary.json
variants.json
differences.txt
```

The files serve different purposes:

* `manifest.json` records the experiment settings, requested model and completion status.
* `request.json` contains the non-secret inputs sent through LiteLLM, including the messages, tool schema, tool choice, model and model parameters.
* `expected_arguments.json` contains the expected answer used during evaluation. It is stored separately and is not sent to the model.
* `evaluation.json` records any fixture-specific accepted-equivalence rules used for the run.
* `responses.jsonl` contains the individual model responses and their evaluation results.
* `summary.json` contains aggregate evaluation metrics.
* `variants.json` groups distinct submitted argument variants.
* `differences.txt` provides a human-readable view of differences between variants.

Keeping the expected arguments and evaluation policy in the run directory allows saved responses to be reanalysed later without making further API calls.

## Defining a fixture

### `experiment.json`

Defines the normal settings for the experiment.

Common settings include:

```json
{
  "model": "bedrock/converse/eu.anthropic.claude-haiku-4-5-20251001-v1:0",
  "runs": 1000,
  "concurrency": 5,
  "max_retries": 10,
  "progress": true,
  "debug": false
}
```

The fixture path is not included because it is supplied as the positional CLI argument.

### `instructions.txt`

Contains the instructions sent to the model. These should explain how to interpret the case and how the tool should be used without exposing the expected answer.

### `case.txt`

Contains the natural-language information from which the model must complete the form.

### `tool_schema.json`

Contains one function-tool definition.

The harness derives both the expected tool name and the JSON Schema used to validate submitted arguments from its `function` object. Fixtures can therefore define different tool names, fields, nested objects, arrays and required properties without adding a shared form model.

### `expected_arguments.json`

Contains the correct arguments for the fixture.

The harness validates these arguments against the fixture's tool schema when the fixture is loaded. An internally inconsistent fixture therefore fails before any model calls are made.

### `evaluation.json`

This file is optional. Most fixtures should omit it and use exact semantic equality.

Include it only when more than one representation should deliberately be treated as correct. For example, the contact fixture permits the flat and street to be split across either address line or combined into one:

```json
{
  "accepted_equivalence_rules": [
    {
      "type": "unordered_text_components",
      "paths": [
        "address.address_line_1",
        "address.address_line_2"
      ]
    }
  ]
}
```

The `unordered_text_components` rule accepts differences only at the listed paths. All non-empty expected strings must appear exactly once across the corresponding submitted strings, and any remaining characters must be whitespace or punctuation. Differences elsewhere still make the submission incorrect.

Accepted alternatives should be introduced deliberately. They make an evaluation more realistic where several representations are genuinely equivalent, but also make its correctness rule less strict.

## Analysing saved results

Analyse a completed or partially completed run with:

```bash
uv run trivial-form-eval analyse runs/<run-id>
```

Analysis requires no API access. It re-evaluates the saved responses using the expected arguments and evaluation policy recorded in the run directory.

## Viewing results in a browser

The repository includes a static HTML viewer for exploring:

* the number and frequency of distinct variants
* field-level differences
* formatted arguments from individual runs

Generate it with:

```bash
uv run python generate_viewer.py
```

This creates:

```text
viewer.html
```

The report is self-contained and does not require a web server. It can be opened directly in a browser, downloaded from a cloud environment or hosted as a static file.

## How results are evaluated

Correctness and repeatability are measured separately.

A model might:

* produce the same wrong answer every time
* return arguments that satisfy the schema but contain the wrong information
* produce the correct answer inconsistently
* vary only in insignificant JSON formatting
* represent an acceptable answer in more than one way

The evaluator therefore reports several distinct measures.

### Raw argument equality

This compares the argument strings recorded by LiteLLM. It is sensitive to differences such as whitespace, key order, escaping and formatting.

With some providers, tool arguments may arrive as structured data and then be serialised by LiteLLM. Raw argument equality should therefore not be interpreted as proof that every output token was generated identically.

### Exact semantic equality

The arguments are parsed as JSON and canonicalised using sorted object keys and compact separators.

Differences in insignificant whitespace and object-key order therefore do not affect this measure. Array order remains significant.

### Accepted semantic correctness

Where a fixture defines accepted-equivalence rules, a submission may be accepted as correct without exactly matching `expected_arguments.json`.

Exact matches and accepted matches are reported separately so that additional tolerated representations remain visible.

### Schema validity

Submitted arguments are validated against the JSON Schema in the selected fixture's `tool_schema.json`.

Schema validity establishes that the arguments have the required structure and permitted value types. It does not establish that they contain the correct information.

For example, a syntactically valid postcode in the correct field may pass schema validation while still being the wrong postcode.

## Tool-call failures

The request forces the fixture's named tool through `tool_choice`, but the evaluator still detects and reports cases where the model produces:

* no tool call
* a prose-only response
* the wrong tool
* multiple tool calls
* malformed JSON arguments
* schema-invalid arguments
* schema-valid but semantically incorrect arguments

## Scope and limitations

A repeated experiment establishes how a particular model behaves for a particular fixed case, tool schema and set of model parameters.

It does not, by itself, establish reliability across:

* different cases using the same form
* different forms or service journeys
* incomplete or ambiguous information
* corrections or conflicting statements
* interactive conversations
* changes in model version or configuration
* workflows involving multiple tools or consequential actions

A model can also produce the same correct answer across many repeated runs while still failing on slightly different cases. Broader reliability therefore requires both repeated runs and a representative set of fixtures or case variants.
