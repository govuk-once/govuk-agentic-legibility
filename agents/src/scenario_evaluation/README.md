# Scenario evaluation

This package compares an implementation-independent evaluation scenario with a
common semantic trace.

It deliberately does not read an implementation's raw trace or know how that
implementation produced the common trace. That keeps the evaluator shared across
implementations.

## Run all scenarios end to end against the current prototype

`run` is an implementation-specific adapter for the current server-driven prototype. It
keeps the scenario and evaluator implementation-independent, but automates the steps needed
to produce a fresh common trace from the journey application.

Before running it:

1. authenticate for the model provider using the normal development credentials;
2. start the mock DVLA service used by the journey application;
3. start the journey application with agent assistance enabled (by default at
   `http://127.0.0.1:8001`).

Run all scenarios for the change-address journey with:

```bash
gds-cli aws <profile> uv run python -m agents.src.scenario_evaluation.run \
  agents/evaluation/scenarios/change-driving-licence-address
```

Or for multiple runs:

```bash
gds-cli aws <profile> \
  uv run python -m agents.src.scenario_evaluation.run \
  agents/evaluation/scenarios/change-driving-licence-address \
  --repeat 10 \
  --concurrency 10
```

For each scenario the runner:

1. starts a journey using the scenario's conversation fixture;
2. reads the agent's `propose_values` output from the implementation raw trace;
3. simulates the user accepting those proposed form values without editing them;
4. submits final confirmation deterministically rather than treating confirmation as an
   agent decision;
5. saves the raw trace under `.traces/evaluation-runs/`;
6. converts it with `agents.src.common_trace`;
7. evaluates the resulting common trace against the scenario.

This is deliberately not an actor-agent simulation. If the implementation does not propose
values needed to continue, the automated run stops rather than filling them from the expected
scenario output. The resulting incomplete trace can still be evaluated and should fail any
expectations that were not met.

Use `--api-base-url` to target another running journey application and `--output-dir` to
store artifacts elsewhere. Other Agentic Legibility implementations can use different runner
adapters as long as they consume the same scenarios and produce the common trace format.

## Run an individual evaluation

First run a scenario through an implementation and convert its raw trace to the
common trace format. Then evaluate that common trace against the scenario:

```bash
uv run python -m agents.src.scenario_evaluation \
  agents/evaluation/scenarios/change-driving-licence-address/manual-entry.yaml \
  path/to/manual-entry.common.yaml
```

A passing evaluation exits with status `0`:

```text
PASS manual-entry: path/to/manual-entry.common.yaml
```

A mismatch exits with status `1` and reports each failed expectation. Invalid or
unsupported input exits with status `2`.

### Asserting an expected evaluation failure

A scenario always describes desired behaviour. Sometimes, however, a developer or
regression test intentionally evaluates a known non-compliant historical trace to
check that the evaluator rejects it. Use `--expect fail` for that assertion:

```bash
uv run python -m agents.src.scenario_evaluation \
  agents/evaluation/scenarios/change-driving-licence-address/manual-entry.yaml \
  agents/examples/common_trace/expected/manual-entry-from-conversation-history.common.yaml \
  --expect fail
```

The command exits with status `0` and reports the assertion itself as a pass while
still showing the evaluation issues that were observed:

```text
PASS manual-entry: evaluation failed as expected: ...
  - expected.assistance.confirm_new_address: unexpected values_proposed event: ...
```

If that trace unexpectedly starts passing the scenario, the command exits with
status `1`. `--expect fail` is only a CLI/testing assertion; it does not change the
scenario or redefine non-compliant behaviour as acceptable.

## Run the known trace regression set

The committed regression manifest pairs scenarios with known common traces and records
whether each trace should pass or fail the behavioural evaluation. This avoids invoking
the single-case CLI manually for every pair:

```bash
uv run python -m agents.src.scenario_evaluation.batch \
  agents/evaluation/regression/common-trace-examples.yaml
```

Expected evaluator failures are reported as passing regression assertions:

```text
PASS manual-entry-compliant
PASS postcode-lookup-compliant
PASS manual-entry-historical (evaluation failed as expected)
PASS postcode-lookup-historical (evaluation failed as expected)

4 cases: 4 passed, 0 failed
```

Use `--verbose` to print the underlying evaluator issues for expected failures. The
manifest is only a regression mapping between scenarios and known traces; expected
outcomes remain defined in the scenario YAML. It does not run an implementation or
generate new traces.

## Expectations are opt-in

A scenario only evaluates dimensions that it declares under `expected`.

For example, this checks only which branch was traversed:

```yaml
expected:
  journey:
    branch: "manual_entry"
```

It does not evaluate assistance or the terminal result. Similarly, a scenario can
check only the final status, or provide both status and result when both matter.

`expected.assistance` is different: when that section is present it is exhaustive.
Any proposal or answer that is not declared there is unexpected output. An empty
`assistance: {}` therefore explicitly means that no assistance should be produced.

## Equivalent representations

Exact equality is the default. A scenario can declare a narrow equivalence rule
where several representations have the same meaning.

The first supported rule is `unordered_text_components`. It allows the same text
to be distributed differently across named fields while still requiring the same
text components overall. This is useful for address lines, where for example these
can represent the same address:

```yaml
address_line_1: "Flat 4"
address_line_2: "81 Station Road"
```

and:

```yaml
address_line_1: "Flat 4, 81 Station Road"
address_line_2: null
```

Rules are explicit and scoped to a comparison target:

```yaml
evaluation:
  accepted_equivalence_rules:
    - type: "unordered_text_components"
      target: "expected.assistance.enter_address_manually.values"
      paths:
        - "address_line_1"
        - "address_line_2"
```

Fields outside the named paths are still compared exactly. Missing or duplicated
text components still fail.

## What version 0.1 evaluates

The evaluator can check:

- journey and conversation-fixture identity;
- expected assistance at each semantic service interaction;
- unexpected assistance when `expected.assistance` is present;
- the semantic branch taken through the current change-address journey;
- terminal journey status and `journey_finished.result`, when specified;
- configured equivalence rules for values that have more than one acceptable
  representation;
- `assistance_failed` events when assistance is being evaluated.

`propose_values` in a scenario maps to `values_proposed` in the common trace. The
scenario and trace vocabularies do not otherwise need to be identical.

Branch evaluation is currently scoped to the prototype
`change-driving-licence-address` journey. It derives the branch from the
service-defined interactions present in the common trace (`enter_address_manually`
or `find_address_by_postcode`). This is service-specific evidence, but not
implementation-specific evidence: different implementations can still be compared
with the same scenario and common trace vocabulary.

The evaluator does not require an exact overall event sequence. It checks only the
behaviour explicitly requested by the scenario and the causal journey evidence
needed for those expectations.
