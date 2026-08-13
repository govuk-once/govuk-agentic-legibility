// helpers for turning common trace events into text
// and GOV.UK tag colours. Used by both the run log page and the comparison
// page, so the same event always looks the same wherever it is shown.

import type { CommonTrace, TerminalStatus, TraceEvent } from "./common-trace";

// Maps a run's terminal status to a GOV.UK tag colour.
export function statusTag(status: TerminalStatus): string {
  switch (status) {
    case "completed":
      return "govuk-tag--green";
    case "blocked":
      return "govuk-tag--orange";
    default:
      return "govuk-tag--grey";
  }
}

// Maps an event type to a GOV.UK tag colour, so the same kind of event is
// easy to spot down a list.
export function eventTag(type: TraceEvent["type"]): string {
  switch (type) {
    case "interaction_available":
      return "govuk-tag--blue";
    case "values_proposed":
      return "govuk-tag--teal";
    case "values_submitted":
      return "govuk-tag--green";
    case "answer_presented":
      return "govuk-tag--purple";
    case "assistance_failed":
      return "govuk-tag--red";
    case "journey_finished":
      return "govuk-tag--orange";
    default:
      return "govuk-tag--grey";
  }
}

// A short, readable label for an event type.
export function eventLabel(type: TraceEvent["type"]): string {
  return type.replaceAll("_", " ");
}

// Renders a single scalar or object value compactly.
function formatValue(value: unknown): string {
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

// Renders a values object as a compact, readable line. An ordinary scalar
// answer stores its value under its own interaction id, so showing that name
// again would just repeat what the interaction already is. It is only shown
// when the object has more than one named part, such as an address split
// into line, town, and postcode.
export function formatValues(values: Record<string, unknown>, interactionId: string): string {
  const entries = Object.entries(values);
  if (entries.length === 1 && entries[0][0] === interactionId) {
    return formatValue(entries[0][1]);
  }
  return entries.map(([key, value]) => `${key}: ${formatValue(value)}`).join(", ");
}

// The one line of detail worth showing for each kind of event.
export function eventDetail(event: TraceEvent): string {
  switch (event.type) {
    case "interaction_available":
      return "-";
    case "values_proposed":
    case "values_submitted":
      return formatValues(event.values, event.interaction_id);
    case "answer_presented":
      return "-";
    case "assistance_failed":
      return "The agent call did not produce a usable result this turn.";
    case "journey_finished":
      return `${Object.keys(event.result).length} value(s) in the final answer`;
    default:
      return "-";
  }
}

// Reorders a run's events so every event for the same interaction sits
// together, in the order they happened to it, rather than interleaved with
// every other interaction's events. An event with no interaction id (such as
// answer presented) is a run-level event, not tied to one interaction, so it
// is kept separate and placed at the end. This never reverses the order of
// one interaction's own events relative to each other, so working out
// whether a value was revised (isRevision, below) gives the same answer
// whichever order the events are shown in.
export function groupEventsByInteraction(events: TraceEvent[]): TraceEvent[] {
  const order: string[] = [];
  const byId = new Map<string, TraceEvent[]>();
  const runEvents: TraceEvent[] = [];
  for (const event of events) {
    const id = "interaction_id" in event ? event.interaction_id : undefined;
    if (!id) {
      runEvents.push(event);
      continue;
    }
    if (!byId.has(id)) {
      order.push(id);
      byId.set(id, []);
    }
    byId.get(id)!.push(event);
  }
  return [...order.flatMap((id) => byId.get(id) ?? []), ...runEvents];
}

// True when an earlier event in the given order already proposed a value for
// this same interaction, so this is a revision rather than the only proposal
// ever made for that field.
export function isRevision(events: TraceEvent[], index: number): boolean {
  const event = events[index];
  if (event.type !== "values_proposed") return false;
  return events
    .slice(0, index)
    .some((earlier) => earlier.type === "values_proposed" && earlier.interaction_id === event.interaction_id);
}

// A readable name for an implementation identifier, for display only (the
// identifier itself stays the stable, machine-readable value elsewhere).
// Strips this app's own prefix when present, then turns the rest into title
// case words.
export function implementationLabel(implementation: string): string {
  const short = implementation.replace(/^agentic-forms-journey-/, "");
  return short
    .split(/[-_]/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

// The last value proposed or submitted for one interaction, read off a
// trace's own events, in the order they happened. Submitted wins over
// proposed, since submission is the interaction's true final answer, but a
// run that never got that far can still be judged on its last proposal.
export interface LastKnownValue {
  values: Record<string, unknown>;
  source: "submitted" | "proposed";
}

export function lastKnownValue(trace: CommonTrace, interactionId: string): LastKnownValue | null {
  const submitted = [...trace.events]
    .reverse()
    .find(
      (event): event is Extract<TraceEvent, { type: "values_submitted" }> =>
        event.type === "values_submitted" && event.interaction_id === interactionId,
    );
  if (submitted) return { values: submitted.values, source: "submitted" };

  const proposed = [...trace.events]
    .reverse()
    .find(
      (event): event is Extract<TraceEvent, { type: "values_proposed" }> =>
        event.type === "values_proposed" && event.interaction_id === interactionId,
    );
  if (proposed) return { values: proposed.values, source: "proposed" };

  return null;
}

// True once this interaction became available at some point in the trace,
// regardless of whether it went on to get a value.
export function wasAvailable(trace: CommonTrace, interactionId: string): boolean {
  return trace.events.some(
    (event) => event.type === "interaction_available" && event.interaction_id === interactionId,
  );
}
