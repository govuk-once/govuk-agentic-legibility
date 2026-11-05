# Sense-check of the Journey Search evaluation dataset

A single run of all 521 scenarios in `scenarios.json` against a local **reference**
Strands agent (`eu.anthropic.claude-sonnet-5-5`), using the **deployed** Journey
Search MCP tool (real tool name, description, schema and responses). This
checks the dataset and the architecture. It does **not** measure how the GOV.UK
orchestrator will perform.

- Runner: `run_evals.py` (design and scoring rules in `RUNNER_NOTES.md`)
- Full traces: `results/full/results.jsonl`; generated summary: `results/full/summary.md`
  (gitignored, local only)
- Cost: 2.37M tokens, no errors or throttling at concurrency 8

## Headline results

| Category | Passed | Search behaviour OK | Expected Form retrieved |
| --- | ---: | ---: | ---: |
| catalogue | 442/464 (95%) | 463/464 | 462/464 |
| clarification | 15/15 | 15/15 | 15/15 |
| no_search | 12/12 | 12/12 | – |
| not_in_catalogue | 10/10 | 10/10 | – |
| similar_services | 10/10 | 10/10 | 10/10 |
| paraphrase | 4/4 | 4/4 | 4/4 |
| named_service | 3/3 | 3/3 | 3/3 |
| unusual | 3/3 | 3/3 | 3/3 |
| **Total** | **499/521 (96%)** | | |

- **Search when required:** 508/509. The one miss is `catalogue_6261`, an internal
  TypeScript retrospective form (see below).
- **No search when forbidden:** 12/12.
- **Correct journey offered:** 477/499 offer_journey scenarios.
- **Clarification:** the agent clarified on turn 1 in 15/15 scenarios, then offered the
  correct journey in 15/15. I read all 15 first-turn questions, and each was relevant and
  listed the right alternatives, so the scripted second message made sense every time.
- **Inappropriate journeys offered:** a different Form was actually offered in
  3 scenarios (`catalogue_3872`, `catalogue_265395`, `catalogue_6296`). None are clear
  agent errors (see below). No journey was offered in any `not_in_catalogue` or
  `no_search` scenario.

## The 22 failures

Every failure is in the `catalogue` category. After reading each transcript:

### A. The request doesn't identify one Form, so the agent reasonably clarified (16)

The agent found the expected Form, but the catalogue holds one or more near-identical
Forms and the request gives no detail that separates them. Asking the citizen is the
behaviour the RFC asks for. **These are dataset defects, not agent failures.**

| Scenario(s) | Competing Forms | What's missing from the request |
| --- | --- | --- |
| `catalogue_1296`, `catalogue_6117` | 1296 / 6117, two feedback forms for deceased military records (MOD vs GOV.UK) | Which organisation or form |
| `catalogue_4119`, `catalogue_7596` | 4119 / 7596, two national security debarment referral forms | Effectively duplicates |
| `catalogue_8092`, `catalogue_264659` | 8092 / 264659, Companies House identity evidence | Effectively duplicates |
| `catalogue_263181`, `_264754`, `_264755`, `_264762` | ~10 location variants of *Immigration Enforcement – first reporting event* | The reporting location (Croydon, Eaton House, etc.) |
| `catalogue_262398` | 262398 / 263924, two MOD EES contact forms | Effectively duplicates |
| `catalogue_266400` | 266400 internal / 266404 external GGSS feedback | That the user is internal |
| `catalogue_6294` | 6294 / 6293, OFSI exception notifications | Which exception |
| `catalogue_7475` | 7475 / 264287, MoJ research screener vs *NIL Awards* variant | Whether they got a nil award |
| `catalogue_7129` | 7129 / 7121, MRRF existing vacancy vs new vacancy | Arguably implied ("add them"); borderline |
| `catalogue_265227` | 265227 share your story / 263217 feedback | Arguably implied ("tell … about my experience"); borderline |

### B. The expected answer looks wrong or the Form shouldn't be in the dataset (5)

| Scenario | Issue |
| --- | --- |
| `catalogue_3872` | Expected *Lettings Information Form – Tenants Room only*. The request says "**I let out** a room", which fits *Rooms Letting Information Form* (1820), and the agent offered that. The ground truth looks wrong, or the request needs to say "I rent a room". |
| `catalogue_3108` | "A family member had a conviction overturned… we need to register." This fits both the Convictions scheme (on behalf of someone) and the *Family Members* Redress Scheme (266184). The agent clarified, which is reasonable. The request needs rewording. |
| `catalogue_265395` | The target is *Copy of Update prison information*, which its description says is "likely used for testing or drafting". The agent offered the original (265021), which is the better answer. Drop this scenario. |
| `catalogue_6261` | *Tell us about your TypeScript familiarity…* is an internal team retrospective form. The agent judged it not a government service and didn't search. Drop this scenario. |
| `catalogue_262674` | Expected *Make a representation*, which is about Companies House identity verification. The request ("make a representation in the consultation") describes a different thing, and search never returned 262674. The request seems to have been written from the title alone. |

### C. Agent or structured-output slips (1)

- `catalogue_6296`: the reply offered only the correct Form, but `workflow_ids` also listed
  the related Ukraine-territory Form. In substance the agent got this right; the scoring
  is strict.

So in this run there are effectively **no real agent selection errors**, and **no
search-tool misses** where the request actually described the Form.

## Catalogue problems

- **Misleading feedback-form titles.** *Visit someone in prison* (263703) and *Get help
  with the cost of prison visits* (8250) are both feedback forms, but their titles read
  like the transactional services. In `outside_book_prison_visit` and
  `outside_claim_prison_visits_cost` the agent read the descriptions and correctly
  rejected them. Keep both scenarios, because they're good tests of the "judge every
  candidate" contract. The titles are a trap for any orchestrator that skims, so a
  `Give feedback:` style prefix in the catalogue would help.
- **Duplicates and near-duplicates** (the table in section A): some have identical titles,
  for example 6482/6535 (GBIS feedback) and 7976/9001 (Find Public Health Resources
  feedback). Those scenarios passed only because their requests repeat details taken
  from the description. Consider deduplicating, or making each title and description say
  what sets it apart (audience, location, MOD vs GOV.UK).
- **Test, copy and internal Forms still in the catalogue**, such as `Copy of …`, the TypeScript
  retrospective, *GGL/GGSS feedback – internal* and the *MRRF Scenario* forms. These are
  worth a look before handover, since the orchestrator will see them in live results too.

## Is the difficulty reasonable?

- **Curated categories:** about right. They show the intended behaviours (multi-search
  on no-match cases, averaging 1.8 searches; sensible rejections; relevant clarifying
  questions). A high pass rate is expected for a capable agent.
- **Catalogue category: easier than real traffic.** Many requests closely paraphrase
  the generated description. The immigration reporting requests are close to verbatim,
  for example. As a result the expected Form was retrieved in 462/464 cases, with about
  one search per scenario. That's fine for a breadth or smoke check, but don't read the 95% as
  evidence about real citizen phrasing.
- **No-journey replies sometimes suggest something nearby**, such as an emergency travel
  document for passports or an HMPPS enquiry form for prison visits, without proposing
  it as the answer. The reference agent left these out of `workflow_ids`, which I think is
  correct. The orchestration team's scoring should treat a conditional suggestion of a
  different service as acceptable.

## Recommendations (scenarios not changed)

1. **Fix the 16 ambiguous catalogue requests** (section A). Either add the
   distinguishing detail, such as the location, internal vs external, or which exception,
   or turn the best pairs into two-turn `clarification` scenarios. The immigration
   location variants would make a good clarification case. Otherwise, any agent that
   behaves as the RFC asks will "fail" them.
2. **Fix or remove the 5 cases in section B**: 3872 (relabel to 1820 or reword), 3108
   (reword), 262674 (rewrite from the description), and remove 265395 and 6261, adding
   them to the excluded list.
3. **Review the remaining test and internal Forms** (MRRF Scenario, *– internal* feedback)
   for exclusion, both from the dataset and ideally from the catalogue.
4. Optionally, **make a few catalogue requests vaguer and more citizen-like** if you want
   more signal on retrieval. This isn't needed for handover.

## Is it ready to hand over?

**Nearly.** The dataset runs end to end, including the scripted multi-turn scenarios, and
the curated categories are sound. The architecture clearly works: a straightforward agent
with only the MCP tool searched when it should, didn't search when it shouldn't, rejected
misleading candidates, and clarified between similar Forms. After the ~21 catalogue
scenario fixes above (1 and 2), I'd expect a capable orchestrator to score close to 100%,
with the remaining failures being informative ones.

This is one run of one reference agent with one prompt (`results/full/run.json`), so it
says nothing about run-to-run variance or about the orchestrator's own prompt and tools.

## Follow-up: dataset fixes (2026-11-05)

These fixes apply the recommendations above. `scenarios.json` now has 519 scenarios
(462 catalogue), and `validate.py` passes.

- **Rewritten (19):** the 16 ambiguous requests in section A, plus 3872, 3108 and 262674
  from section B. Each now includes the detail that separates the expected Form, taken
  from its catalogue description. Examples: the reporting location; internal user;
  "exception for required payments"; tenant rather than landlord; executor of someone
  whose conviction was quashed; an overdue Companies House identity verification
  statement. 3872 keeps its original label, with the request reworded for a tenant.
- **Removed (2):** `catalogue_265395` (copy of 265021) and `catalogue_6261` (internal
  TypeScript retrospective). No honest request can target them. README counts are updated.
- **Re-run** (`results/fixes/`): **19/19 passed**. Spot-checked replies show the agent
  choosing because of the added detail (for example, address history for 264659 vs 8092).
- `catalogue_6296` was left as it is. It was a structured-output slip by the agent, not a
  dataset problem.

Caveat: some pairs (4119/7596, 8092/264659, 262398/263924) are effectively duplicate
Forms. Their requests now quote form-level details that a real citizen might not know.
The underlying fix belongs in the catalogue (deduplicate, or say clearly in the
title and description what sets each one apart).
