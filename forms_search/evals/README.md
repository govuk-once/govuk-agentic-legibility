# Journey Search — orchestration evaluation scenarios

This is a **synthetic end-to-end evaluation dataset** for the GOV.UK orchestrator using Legibility's `search_service_journeys` MCP tool. The aim is to check whether the orchestrator uses search when appropriate, identifies and offers the intended Form, asks for clarification where needed, and does not offer an unsuitable Form.

It is **not** a vector-search ranking benchmark. These are proof-of-concept scenarios: none of the Forms needs to be executable, and the test must not submit real applications.

## Files

- **`scenarios.json`** — the **single source of truth**, edited directly. Contains 521 scenarios.
- **`validate.py`** — checks the JSON structure, unique scenario IDs, expected outcomes and workflow IDs against `forms_search/data/catalogue.json`. Uses only Python's standard library.

There is **no generation or build step**. The orchestration team supplies the runner that executes these scenarios against its agent; this directory contains the scenarios and a dataset validator, not the runner.

## What is in the dataset?

There are **521 scenarios**: **464 catalogue-derived** requests (one for each selected Form) and **57 curated** scenarios. **506 have one citizen turn; 15 have two**. All scenario categories currently in the file are listed below.

| `category` | Count | What it tests |
| --- | ---: | --- |
| `catalogue` | 464 | A straightforward citizen request intended to lead to a particular Form in the catalogue. Broad coverage of the available Forms. |
| `clarification` | 15 | An initially ambiguous request, followed by a scripted citizen reply that resolves the ambiguity and points to one specific Form. All have two turns. |
| `no_search` | 12 | A question or conversational message that should **not** trigger Journey Search (for example, a greeting or general information request). |
| `not_in_catalogue` | 10 | A plausible government service request that should prompt a search, but has **no suitable Form in this catalogue**. The agent should not offer a Legibility journey simply because a candidate was returned. |
| `similar_services` | 10 | A sufficiently specific request where two or more Forms could sound similar, but **one particular Form** is intended. |
| `paraphrase` | 4 | A relevant Form described in everyday language rather than its official title. |
| `named_service` | 3 | A request using the service's specific name or terminology. |
| `unusual` | 3 | A less obvious or specialised service which the orchestrator should still be able to discover. |
| **Total** | **521** | |

`category` is only a reporting label, not an instruction to the runner. These are the eight values **currently used**; the validator permits other non-empty category strings if you add more scenarios.

The large `catalogue` group checks breadth of discovery. The curated groups check the other decisions set out in the Journey Search contract. **Report results by category** as well as overall: 464 catalogue cases would otherwise dominate the total and conceal failures on no-search or clarification cases.

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

The **orchestration team owns the runner**. For each scenario:

1. Start a fresh conversation with the orchestrator; send the first `user` message.
2. Record the agent's reply and Journey Search MCP calls. Evaluate the expected response for that turn.
3. If another turn exists and the agent has clarified appropriately, send the next `user` message verbatim and check its expected outcome.
4. Check the scenario-level `search` requirement, then record pass/fail and the trace.

The runner should be able to observe which **workflow ID was offered**; if the agent only returns free text, that result needs to be inspected rather than inferring success from what the search tool returned. There is no requirement to execute a journey. A simple pass/fail result, recorded tool calls, and manual review of uncertain responses are sufficient at this stage.

## Validating the JSON

From the **repository root**, using the same `uv` convention as the rest of the repo:

```bash
uv run python -m forms_search.evals.validate
```

This checks dataset structure and workflow IDs against the catalogue. It does **not** call the MCP server or test the orchestrator. Edit `scenarios.json` directly and rerun this command; it does not regenerate or overwrite anything.

## Limitations

The source catalogue contains 547 Forms. The initial dataset excluded 83 entries, mostly marked as tests, demos, archived, or otherwise unsuitable, leaving 464 catalogue-derived cases. The citizen requests are synthetic; some were generated from descriptions similar to those used by the search index. They are useful for checking the PoC architecture but are **not** a representative sample of real citizens' requests or a production assurance benchmark.

A matching workflow ID is a ground-truth label for the purposes of this test, **not** an independently verified eligibility decision or a claim that the Form is live. The curated `not_in_catalogue` judgements also refer to the catalogue snapshot; review them if the catalogue changes.
