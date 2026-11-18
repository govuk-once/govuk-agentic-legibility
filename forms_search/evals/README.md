# Journey Search — orchestration evaluation scenarios

This is a **synthetic end-to-end evaluation dataset** for the GOV.UK orchestrator using Legibility's `search_service_journeys` MCP tool. The aim is to check whether the orchestrator uses search when appropriate, identifies and offers the intended Form, asks for clarification where needed, and does not offer an unsuitable Form.

It is **not** a vector-search ranking benchmark. These are proof-of-concept scenarios: none of the Forms needs to be executable, and the test must not submit real applications.

## In brief, for the orchestration team

1. **Read** [What is in the dataset?](#what-is-in-the-dataset) and [Scenario fields and allowed outcomes](#scenario-fields-and-allowed-outcomes).
2. **Optionally, run our reference runner first** ([below](#our-reference-runner)). It confirms your Journey Search access works and shows the kind of output to expect. With a plain Strands agent that has only the Journey Search tool, we expect **about 518/519**.
3. **Run the scenarios against your orchestrator** with your own runner, following [Running against your orchestrator](#running-against-your-orchestrator) and the [scoring rules](#scoring-rules).
4. **Report results by category** and keep the traces, so failures can be told apart: dataset, search tool, or orchestrator.

Your orchestrator has more tools, different prompts, guardrails and other behaviour that our reference agent doesn't. Measuring how those affect journey discovery is part of the point, so we don't expect your results to match ours.

## Files

- **`scenarios.json`**: the **single source of truth**, edited directly. Contains 519 scenarios.
- **`validate.py`**: checks the JSON structure, unique scenario IDs, expected outcomes and workflow IDs against `forms_search/data/catalogue.json`. Uses only Python's standard library.
- **`run_evals.py`**: our **reference runner**. It runs the scenarios against a simple Strands agent that uses the deployed Journey Search MCP tool. It's an example, not the official runner.
- **`report.md`**: our assessment of the dataset from the reference run, including the fixes made since.

There is **no generation or build step**. The orchestration team runs these scenarios against its own agent. `run_evals.py` shows one way to do it.

## What is in the dataset?

There are **519 scenarios**: **462 catalogue-derived** requests (one for each selected Form) and **57 curated** scenarios. **504 have one citizen turn; 15 have two**. All scenario categories currently in the file are listed below.

| `category` | Count | What it tests |
| --- | ---: | --- |
| `catalogue` | 462 | A straightforward citizen request intended to lead to a particular Form in the catalogue. Broad coverage of the available Forms. |
| `clarification` | 15 | An initially ambiguous request, followed by a scripted citizen reply that resolves the ambiguity and points to one specific Form. All have two turns. |
| `no_search` | 12 | A question or conversational message that should **not** trigger Journey Search (for example, a greeting or general information request). |
| `not_in_catalogue` | 10 | A plausible government service request that should prompt a search, but has **no suitable Form in this catalogue**. The agent should not offer a Legibility journey simply because a candidate was returned. |
| `similar_services` | 10 | A sufficiently specific request where two or more Forms could sound similar, but **one particular Form** is intended. |
| `paraphrase` | 4 | A relevant Form described in everyday language rather than its official title. |
| `named_service` | 3 | A request using the service's specific name or terminology. |
| `unusual` | 3 | A less obvious or specialised service which the orchestrator should still be able to discover. |
| **Total** | **519** | |

`category` is only a reporting label, not an instruction to the runner. These are the eight values **currently used**; the validator permits other non-empty category strings if you add more scenarios.

The large `catalogue` group checks breadth of discovery. The curated groups check the other decisions set out in the Journey Search contract. **Report results by category** as well as overall: 462 catalogue cases would otherwise dominate the total and conceal failures on no-search or clarification cases.

### Simple, single-turn scenarios

Most scenarios consist of one citizen message and one expected outcome. For example:

```json
{
  "id": "catalogue_1994",
  "category": "catalogue",
  "search": "required",
  "turns": [
    {
      "user": "The MOT record for my car has the wrong mileage on it. How can I get that fixed?",
      "expect": "offer_journey",
      "workflow_id": "1994"
    }
  ]
}
```

Success means the orchestrator offers **workflow `1994`** to the citizen. Returning it in an MCP search result is not enough. The agent can choose its own query and may search more than once; the test does not prescribe a sequence of tool calls.

### Ambiguous, two-turn scenarios

These test clarification rather than accepting several alternative workflow IDs. The first citizen message is deliberately insufficient to select one Form. The second message resolves the ambiguity and has **one expected workflow ID**.

```json
{
  "id": "cancelled_test_theory",
  "category": "clarification",
  "search": "required",
  "turns": [
    {
      "user": "I want to claim expenses because my test was cancelled.",
      "expect": "clarify"
    },
    {
      "user": "It was my car theory test, not the practical test.",
      "expect": "offer_journey",
      "workflow_id": "6770"
    }
  ]
}
```

**How to run a scripted clarification:**

1. Start a fresh conversation and send the first `user` string.
2. Check that the orchestrator asks a **relevant clarifying question** rather than committing to a journey. Its wording need not match anything in the dataset.
3. If it does, send the second `user` string **verbatim**, exactly as stored in the JSON, and check that it offers the specified workflow ID.
4. If it does not clarify appropriately, mark the scenario as failed. Do not treat sending the second message as proof that the agent handled the first turn correctly.

This is a **deliberately simple scripted citizen**, not a simulated user. The second message is fixed: the runner does **not** generate a reply tailored to the particular wording of the agent's question. It assumes the agent asks a relevant question to which the scripted answer makes sense. There is no need for an LLM user simulator for this PoC.

### Search required, but no matching Form

A `not_in_catalogue` scenario has `"search": "required"` and `"expect": "no_journey"`. For example, a citizen wants to renew a passport: the orchestrator should attempt service discovery but **not** propose a Legibility Form when none of the returned candidates is suitable. It may instead help through another capability. This tests rejection of misleading candidates, not detection of whether government offers the service in general.

### No search required

A `no_search` scenario has `"search": "forbidden"` and `"expect": "no_journey"`, such as "Hello! How are you?" or a straightforward factual question. The orchestrator should not invoke Journey Search at all. It can still respond normally or use a different tool.

## Scenario fields and allowed outcomes

Each scenario has four fields:

| Field | Meaning |
| --- | --- |
| `id` | Unique, stable scenario identifier. |
| `category` | Reporting group (see all current values above). |
| `search` | `required` = call `search_service_journeys` at least once **during the entire scenario**; `forbidden` = do not call it at all. No specified timing, query string, or maximum number of calls. |
| `turns` | Ordered array of citizen messages with the expected response after each. |

Each turn has `user` (the exact text to send), `expect`, and — only for `offer_journey` — `workflow_id` (a **string**, even when numeric-looking).

| `expect` | What it means |
| --- | --- |
| `offer_journey` | The agent proposes the **specific** `workflow_id` to the citizen. The ID merely appearing among MCP candidates does not count, and no execution is required. |
| `clarify` | The agent asks an appropriate question to resolve ambiguity, without prematurely selecting a journey. This is used on the first turn of the 15 clarification scenarios. |
| `no_journey` | The agent does **not** propose a Legibility Form. Answering normally or using another capability is allowed. |

The `search` requirement is checked at scenario level, independently of the conversational outcome. For instance, a `not_in_catalogue` case should both invoke search **and** avoid offering an unsuitable journey.

## Running the evaluation

### Running against your orchestrator

The **orchestration team owns its runner**. For each scenario:

1. Start a **fresh conversation**, so scenarios can't affect each other, and send the first `user` message.
2. Record the agent's reply, the **workflow ID(s) it offered**, and every `search_service_journeys` call with its query and returned candidates. Score that turn.
3. If there's another turn **and the agent clarified**, send the next `user` message **verbatim** and score it. If it didn't clarify, stop: the scenario has failed.
4. Check the scenario-level `search` requirement, then record pass or fail along with the trace.

Never show the agent `expect`, `workflow_id` or `category`; it only sees the `user` text. Let it choose whether to search, what to search for, and how many times.

Your runner needs a reliable way to see **which workflow ID the agent offered**. That could be a structured decision, a "start journey" tool call that the citizen hasn't yet confirmed, or similar. If the agent only produces free text, review those results by hand. Don't infer success from what the search tool returned.

### Scoring rules

These are the rules `run_evals.py` applies. A scenario passes only if all of them hold.

| Check | Passes when |
| --- | --- |
| `search: required` | At least one `search_service_journeys` call anywhere in the scenario. |
| `search: forbidden` | No `search_service_journeys` calls at all. |
| `offer_journey` turn | The agent offers exactly one journey, and it's the expected `workflow_id`. |
| `clarify` turn | The agent asks a question, or offers a choice, instead of committing to a journey. Check by hand that the question is relevant. |
| `no_journey` turn | The agent offers no journey. Answering normally, pointing to GOV.UK guidance or using another capability is fine. |

Two things worth recording **separately** from pass/fail, because they help explain failures:

- **Expected ID retrieved?** Did any search return the expected `workflow_id`? If not, the miss is in the query or the search. If it was returned but not offered, the miss is the orchestrator's decision.
- **Other journeys offered**: any workflow ID offered that wasn't the expected one.

### Suggested output

A machine-readable record per scenario, plus a short summary. Our runner writes one JSON line per scenario (`results.jsonl`), like this:

```json
{
  "id": "catalogue_264762",
  "category": "catalogue",
  "turns": [
    {
      "user": "I need to provide personal, household, health, work and identity details before my first immigration reporting appointment at the Glasgow reporting centre, ...",
      "searches": [
        {
          "input": {"query": "provide personal, household, health, work and identity details before first immigration reporting appointment ..."},
          "status": "success",
          "candidates": [
            {"workflow_id": "264762", "title": "Immigration Enforcement – first reporting event: Glasgow"},
            {"workflow_id": "264755", "title": "Immigration Enforcement – first reporting event: Loughborough"}
          ]
        }
      ],
      "outcome": "offer_journey",
      "workflow_ids": ["264762"],
      "reply": "This looks like the right form: \"Immigration Enforcement – first reporting event: Glasgow\". ... Would you like to start it?"
    }
  ],
  "seconds": 9.5,
  "usage": {"inputTokens": 4189, "outputTokens": 295, "totalTokens": 4484},
  "messages": ["... full agent transcript ..."]
}
```

It also writes a `summary.md` with these sections:

- pass rate overall and **by category**
- search compliance and whether the expected ID was retrieved
- correct-journey rate and clarification results
- each failure with its queries, candidates, the agent's decision and its reply

You don't need to use the same format. Keep enough of each trace that someone can see *why* a scenario failed.

### Our reference runner

`run_evals.py` drives a deliberately plain agent: a Strands agent running `eu.anthropic.claude-sonnet-5-5` on Bedrock. It has a short, generic system prompt and **only** the Journey Search tool. It connects to the **deployed** MCP server the same way as [`journey_search/examples/strands_client.py`](../journey_search/examples/strands_client.py), which it imports. At the end of each turn the agent records a structured decision (`reply`, `outcome`, `workflow_ids`), so scoring is deterministic. The agent still makes every decision itself.

It's a self-contained `uv` script. It needs this repository's layout, the five `JOURNEY_SEARCH_*` settings from [CONNECTING.md](../journey_search/CONNECTING.md), and AWS credentials with Bedrock access for the model. From the **repository root**:

```bash
# A handful of scenarios, to check access and see the output
uv run forms_search/evals/run_evals.py run --run smoke --ids unusual_octopus cancelled_test_theory no_search_greeting outside_passport_renewal

# A sample per category, a whole category, or everything
uv run forms_search/evals/run_evals.py run --run sample --per-category 5
uv run forms_search/evals/run_evals.py run --run clar --category clarification
uv run forms_search/evals/run_evals.py run --run full --concurrency 8

# Rebuild summary.md from saved results without calling the agent
uv run forms_search/evals/run_evals.py report --run full
```

Results go to `forms_search/evals/results/<run>/`: `results.jsonl`, `summary.md`, and `run.json`, which records the model, system prompt, decision schema and the tool spec as the server served it. Re-running with the same `--run` name resumes, skipping scenarios that already completed. `results/` is gitignored.

A full run takes about 5 minutes at concurrency 8 and uses roughly **2.4M tokens**, about 5k per scenario.

**What to expect:** about **518/519**, with every curated category at 100%. Our full run was 499/521 before the dataset fixes described in `report.md`. The 21 problem scenarios have since been fixed or removed, and the 19 rewritten ones then passed 19/19. The one known remaining failure, `catalogue_6296`, was a slip by the agent, not a dataset problem. Expect a scenario or two to change between runs.

**What the reference result does and doesn't tell you:** it shows the dataset is executable and solvable, and that a simple agent can find journeys through the MCP tool, including by clarifying and searching again. It says **nothing** about your orchestrator. Your extra tools, prompts, guardrails and conversation handling could make search happen more or less often, change queries, or change how candidates are judged. That difference is what we'd like you to measure and report back.

## Validating the JSON

From the **repository root**, using the same `uv` convention as the rest of the repo:

```bash
uv run python -m forms_search.evals.validate
```

This checks dataset structure and workflow IDs against the catalogue. It does **not** call the MCP server or test the orchestrator. Edit `scenarios.json` directly and rerun this command; it does not regenerate or overwrite anything.

## Limitations

The source catalogue contains 547 Forms. The dataset excludes 85 entries, mostly marked as tests, demos, archived, copies, internal, or otherwise unsuitable, leaving 462 catalogue-derived cases. The citizen requests are synthetic; some were generated from descriptions similar to those used by the search index. They are useful for checking the PoC architecture but are **not** a representative sample of real citizens' requests or a production assurance benchmark.

A matching workflow ID is a ground-truth label for the purposes of this test, **not** an independently verified eligibility decision or a claim that the Form is live. The curated `not_in_catalogue` judgements also refer to the catalogue snapshot; review them if the catalogue changes.
