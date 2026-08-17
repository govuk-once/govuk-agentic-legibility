// Generates synthetic comparator methods from a REAL common trace.
//
// The comparison only works when methods ran the same journey. So rather
// than create fixed comparators on a fictional journey, these are derived from
// whatever real trace the user loads: same journey, same interactions, same
// final answers, just reached a different way.
//

import {
  IMPLEMENTATION_AGGRESSIVE_SYNTHETIC,
  IMPLEMENTATION_VERBOSE_SYNTHETIC,
  type CommonTrace,
  type TraceEvent,
} from "./common-trace";

// Every value in an object, replaced with a placeholder, so a synthetic
// "still drafting" proposal is obviously not a real guess.
function placeholderValues(values: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.keys(values).map((key) => [key, "…"]));
}

// A single-pass comparator: keeps only the LAST proposal for each
// interaction (dropping any earlier revisions) and drops any assistance
// failures, modelling a method that filled everything in one go with no
// back-and-forth. The final submitted answers are unchanged.
function singlePassFrom(base: CommonTrace, runId: string): CommonTrace {
  const lastProposalIndex = new Map<string, number>();
  base.events.forEach((event, i) => {
    if (event.type === "values_proposed") lastProposalIndex.set(event.interaction_id, i);
  });

  const events: TraceEvent[] = base.events.filter((event, i) => {
    if (event.type === "assistance_failed") return false;
    if (event.type === "values_proposed") return lastProposalIndex.get(event.interaction_id) === i;
    return true;
  });

  return {
    ...base,
    source_trace: null,
    run: { ...base.run, id: runId, implementation: IMPLEMENTATION_AGGRESSIVE_SYNTHETIC },
    events,
  };
}

// A revision-heavy comparator: gives every interaction an extra placeholder
// proposal before its real first proposal, modelling a method that drafts
// an answer before settling on it. Any revisions or failures already in the
// base trace are kept, so this only ever adds more back-and-forth, never
// less. The final submitted answers are unchanged.
function revisionHeavyFrom(base: CommonTrace, runId: string): CommonTrace {
  const firstProposalIndex = new Map<string, number>();
  base.events.forEach((event, i) => {
    if (event.type === "values_proposed" && !firstProposalIndex.has(event.interaction_id)) {
      firstProposalIndex.set(event.interaction_id, i);
    }
  });

  const events: TraceEvent[] = [];
  base.events.forEach((event, i) => {
    if (event.type === "values_proposed" && firstProposalIndex.get(event.interaction_id) === i) {
      events.push({ type: "values_proposed", interaction_id: event.interaction_id, values: placeholderValues(event.values) });
    }
    events.push(event);
  });

  return {
    ...base,
    source_trace: null,
    run: { ...base.run, id: runId, implementation: IMPLEMENTATION_VERBOSE_SYNTHETIC },
    events,
  };
}

// Produces revision-heavy and single-pass comparators for the given real
// trace, on the same journey so they can be compared against it directly.
// Run ids are supplied by the caller rather than generated here, matching
// this file's pure, no-side-effects style: it does not read the clock or
// create ids of its own.
export function deriveComparators(base: CommonTrace, runIds: { revisionHeavy: string; singlePass: string }): CommonTrace[] {
  return [revisionHeavyFrom(base, runIds.revisionHeavy), singlePassFrom(base, runIds.singlePass)];
}
