// Pure helpers that turn a set of common traces into the numbers and rows the
// comparison page renders. No framework or server dependency; everything is
// derived from the traces themselves.
//
// Framing: one method is the REFERENCE (a baseline) and the others are
// CANDIDATES measured against it. The common trace shows how many
// times a method had to propose a value, and whether it needed the agent to
// recover from a failed turn.

import type { CommonTrace, TerminalStatus } from "./common-trace";
import { lastKnownValue, wasAvailable } from "./trace-display";

// One method loaded into the comparison. `id` is a unique key; `label` is
// the human-facing name, which does not need to be globally unique because
// only one journey's methods are shown at a time.
export interface Method {
  id: string;
  label: string;
  trace: CommonTrace;
}

// A set of methods that all ran the same journey: the unit within which a
// fair comparison can be drawn.
export interface JourneyGroup {
  journeyId: string;
  journeyName: string | null;
  methods: Method[];
}

// Groups loaded methods by the journey they ran, largest group first.
// Methods can only be compared within a group, because comparing across
// different journeys (different questions/branching) is not like-for-like.
export function groupByJourney(methods: Method[]): JourneyGroup[] {
  const groups = new Map<string, JourneyGroup>();
  for (const method of methods) {
    const id = method.trace.run.journey_id;
    let group = groups.get(id);
    if (!group) {
      group = { journeyId: id, journeyName: method.trace.initial_context?.form.name ?? null, methods: [] };
      groups.set(id, group);
    }
    group.methods.push(method);
  }
  return [...groups.values()].sort((a, b) => b.methods.length - a.methods.length);
}

// Event-count figures for a single method.
export interface MethodMetrics {
  status: TerminalStatus;
  interactionsAvailable: number;
  valuesProposed: number;
  valuesSubmitted: number;
  assistanceFailures: number;
  answerPresented: boolean;
}

export function methodMetrics(trace: CommonTrace): MethodMetrics {
  const events = trace.events;
  return {
    status: trace.run.status,
    interactionsAvailable: new Set(
      events.filter((e) => e.type === "interaction_available").map((e) => e.interaction_id),
    ).size,
    valuesProposed: events.filter((e) => e.type === "values_proposed").length,
    valuesSubmitted: events.filter((e) => e.type === "values_submitted").length,
    assistanceFailures: events.filter((e) => e.type === "assistance_failed").length,
    answerPresented: events.some((e) => e.type === "answer_presented"),
  };
}

// A scorecard row: one metric across every method.
export interface ScorecardRow {
  label: string;
  display: string[];
  better: "lower" | "higher" | null;
  bestIndexes: number[];
}

export interface Scorecard {
  rows: ScorecardRow[];
}

// Works out which method(s) win a row. Ties and all-equal rows produce no
// winner.
function bestIndexes(values: (number | null)[], better: "lower" | "higher" | null): number[] {
  if (!better) return [];
  const entries = values.map((v, i) => ({ v, i })).filter((e): e is { v: number; i: number } => e.v !== null);
  if (entries.length < 2) return [];
  const nums = entries.map((e) => e.v);
  const target = better === "lower" ? Math.min(...nums) : Math.max(...nums);
  if (nums.every((n) => n === target)) return [];
  return entries.filter((e) => e.v === target).map((e) => e.i);
}

export function buildScorecard(methods: Method[]): Scorecard {
  const metrics = methods.map((m) => methodMetrics(m.trace));

  const numberRow = (label: string, pick: (m: MethodMetrics) => number, better: "lower" | "higher" | null): ScorecardRow => {
    const values = metrics.map(pick);
    return { label, display: values.map(String), better, bestIndexes: bestIndexes(values, better) };
  };

  return {
    rows: [
      { label: "Status", display: metrics.map((m) => m.status), better: null, bestIndexes: [] },
      numberRow("Interactions made available", (m) => m.interactionsAvailable, null),
      numberRow("Values proposed", (m) => m.valuesProposed, "lower"),
      numberRow("Values submitted", (m) => m.valuesSubmitted, null),
      numberRow("Assistance failures", (m) => m.assistanceFailures, "lower"),
      {
        label: "Answer presented",
        display: metrics.map((m) => (m.answerPresented ? "yes" : "no")),
        better: null,
        bestIndexes: [],
      },
    ],
  };
}

// One interaction's outcome within a single trace: whether it was reached at
// all, and, if so, the last value known for it.
export interface InteractionOutcome {
  reached: boolean;
  values: Record<string, unknown> | null;
  source: "submitted" | "proposed" | null;
}

function readInteraction(trace: CommonTrace, interactionId: string): InteractionOutcome {
  const known = lastKnownValue(trace, interactionId);
  return { reached: wasAvailable(trace, interactionId), values: known?.values ?? null, source: known?.source ?? null };
}

function sameOutcome(a: InteractionOutcome, b: InteractionOutcome): boolean {
  return a.source === b.source && JSON.stringify(a.values) === JSON.stringify(b.values);
}

// One candidate method's outcome for an interaction, relative to the
// reference.
export interface DivergenceCandidate extends InteractionOutcome {
  id: string;
  label: string;
  differs: boolean;
}

// One interaction's outcome: the reference's, plus each candidate's.
export interface DivergenceRow {
  interactionId: string;
  reference: InteractionOutcome;
  candidates: DivergenceCandidate[];
}

export interface Divergence {
  journeyId: string;
  journeyName: string | null;
  referenceLabel: string;
  candidateColumns: { id: string; label: string }[];
  rows: DivergenceRow[];
}

// Per-interaction divergence is measured against the REFERENCE method (by
// id). Callers are expected to pass methods already scoped to one journey
// group, since comparing across journeys is not like-for-like.
export function buildDivergence(methods: Method[], referenceId: string | null): Divergence | null {
  if (methods.length < 2) return null;

  const reference = methods.find((m) => m.id === referenceId) ?? methods[0];
  const candidates = methods.filter((m) => m.id !== reference.id);
  if (candidates.length < 1) return null;

  // Interaction order: the reference's own order of first appearance, then
  // any interaction candidates reached that the reference never did.
  const order: string[] = [];
  const seen = new Set<string>();
  const register = (trace: CommonTrace) => {
    for (const event of trace.events) {
      if ("interaction_id" in event && event.interaction_id && !seen.has(event.interaction_id)) {
        seen.add(event.interaction_id);
        order.push(event.interaction_id);
      }
    }
  };
  register(reference.trace);
  candidates.forEach((c) => register(c.trace));

  const rows: DivergenceRow[] = order.map((interactionId) => {
    const refOutcome = readInteraction(reference.trace, interactionId);
    const candidateCells: DivergenceCandidate[] = candidates.map((c) => {
      const outcome = readInteraction(c.trace, interactionId);
      return { id: c.id, label: c.label, ...outcome, differs: !sameOutcome(refOutcome, outcome) };
    });
    return { interactionId, reference: refOutcome, candidates: candidateCells };
  });

  return {
    journeyId: reference.trace.run.journey_id,
    journeyName: reference.trace.initial_context?.form.name ?? null,
    referenceLabel: reference.label,
    candidateColumns: candidates.map((c) => ({ id: c.id, label: c.label })),
    rows,
  };
}
