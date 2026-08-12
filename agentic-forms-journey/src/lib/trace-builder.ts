// Turns a form's contract and the running state of a conversation into a
// common trace, turn by turn. This reuses the same branch resolution logic as
// the existing journey flow view, so an interaction becomes available at
// exactly the point a user would expect to see it: once its
// branch gating has resolved, not before.
//
// This file has no side effects of its own. It does not create a run id,
// read the clock, or call any API. Whatever code runs the conversation must
// create the run id itself, and must tell this module directly whether each
// turn succeeded or failed, and when the user's journey has actually
// finished.

import type { AgentContract } from "./server/engine-types";
import { buildJourneyFlow } from "./server/flow";
import { SCHEMA_VERSION, type CommonTrace, type TerminalStatus, type TraceEvent } from "./common-trace";

// Shapes one field's value into the flat values object the common trace
// expects. An object answer, such as an address, has its own named parts
// spread directly, matching how the shared format represents
// answers with multiple parts. Anything else, including a list of selected checkboxes, sits under
// the field's own key.
export function shapeValues(value: unknown, key: string): Record<string, unknown> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return { ...(value as Record<string, unknown>) };
  }
  return { [key]: value };
}

// Starts a new, empty common trace for one run. Call this once, before the
// first turn.
export function startTrace(run: {
  id: string;
  journeyId: string;
  implementation: string;
  sourceTrace: string | null;
  form: { id: string; name: string | null; sha256: string };
}): CommonTrace {
  return {
    schema_version: SCHEMA_VERSION,
    source_trace: run.sourceTrace,
    run: {
      id: run.id,
      journey_id: run.journeyId,
      implementation: run.implementation,
      status: "incomplete",
    },
    initial_context: { form: run.form },
    events: [],
  };
}

// What happened on one turn. When ok is false, the agent call itself did not
// produce a usable result, so answers and awaitingInput are not meaningful.
export type TraceTurn =
  | { ok: true; answers: Record<string, unknown> }
  | { ok: false };

// Advances a trace by one turn. Works out which interactions have become
// available now their branch gating has resolved, and which values were
// newly proposed or changed since the last turn. Records an assistance
// failed event instead when the turn itself did not succeed. Returns a new
// trace; the one passed in is never changed.
export function appendTurn(trace: CommonTrace, contract: AgentContract, turn: TraceTurn): CommonTrace {
  const events: TraceEvent[] = [...trace.events];

  if (!turn.ok) {
    events.push({ type: "assistance_failed" });
    return { ...trace, events };
  }

  const flow = buildJourneyFlow(contract, turn.answers);

  // A question already known to be reachable does not need to be announced
  // again, so this is built once from what has already happened.
  const alreadyAvailable = new Set(
    events
      .filter((event): event is Extract<TraceEvent, { type: "interaction_available" }> =>
        event.type === "interaction_available",
      )
      .map((event) => event.interaction_id),
  );

  for (const node of flow) {
    // A skipped question never becomes available. An undetermined one might
    // still resolve on a later turn, so it is left alone rather than guessed.
    if (node.status.state === "skipped" || node.status.state === "undetermined") continue;

    if (!alreadyAvailable.has(node.key)) {
      events.push({ type: "interaction_available", interaction_id: node.key });
    }

    if (node.status.state === "answered") {
      const values = shapeValues(turn.answers[node.key], node.key);

      // Only a genuinely new or changed value is worth another proposal. The
      // shared format does not want a note saying an earlier proposal was
      // replaced, so this simply looks at what was proposed most recently.
      const lastProposed = [...events]
        .reverse()
        .find(
          (event): event is Extract<TraceEvent, { type: "values_proposed" }> =>
            event.type === "values_proposed" && event.interaction_id === node.key,
        );
      const changed = !lastProposed || JSON.stringify(lastProposed.values) !== JSON.stringify(values);

      if (changed) {
        events.push({ type: "values_proposed", interaction_id: node.key, values });
      }
    }
  }

  return { ...trace, events };
}

// Closes out a trace once the journey has reached a final outcome. Emits
// one values submitted event per field that made it into the final answers,
// then one journey finished event, and an answer presented event if the
// journey completed cleanly. This app has no separate review step, so
// submission happens once, using whichever values survived to this
// point rather than at the moment each field was first answered.
//
// Call this once, the first time the conversation actually concludes. It is
// safe to call again on an already finished trace: nothing further happens.
export function finishJourney(
  trace: CommonTrace,
  finalAnswers: Record<string, unknown>,
  status: Exclude<TerminalStatus, "incomplete">,
): CommonTrace {
  if (trace.run.status !== "incomplete") return trace;

  const events: TraceEvent[] = [...trace.events];
  const availableIds = new Set(
    events
      .filter((event): event is Extract<TraceEvent, { type: "interaction_available" }> =>
        event.type === "interaction_available",
      )
      .map((event) => event.interaction_id),
  );

  for (const [key, value] of Object.entries(finalAnswers)) {
    // Only submit a field the journey actually reached. This should always be
    // true in practice, but guards against submitting something the journey
    // never made available.
    if (!availableIds.has(key)) continue;
    events.push({ type: "values_submitted", interaction_id: key, values: shapeValues(value, key) });
  }

  events.push({ type: "journey_finished", status, result: finalAnswers });

  if (status === "completed") {
    events.push({ type: "answer_presented" });
  }

  return { ...trace, events, run: { ...trace.run, status } };
}
