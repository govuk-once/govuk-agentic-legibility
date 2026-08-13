// Client-side store holding the common trace and raw trace for the current
// run.
//
// The agent runs on the home page, but the trace is viewed on /log, so it has
// to outlive a navigation. It lives in a runes store and is mirrored to
// sessionStorage so a refresh of /log, or landing there directly, still shows
// the latest run. A new form clears it.
//
// This is the only place in the app that creates a run id or decides when a
// turn succeeded, failed, or brought the journey to a close: trace-builder.ts
// and raw-trace.ts are both pure and expect exactly this from whatever runs
// the conversation.

import type { BranchRule, MappingRow } from "$lib/server/engine-types";
import { IMPLEMENTATION_AGENT, type CommonTrace, type TerminalStatus } from "$lib/common-trace";
import { appendTurn, finishJourney, startTrace } from "$lib/trace-builder";
import { appendRawTurn, rawTraceFilename, startRawTrace, type RawTrace } from "$lib/raw-trace";

const STORAGE_KEY = "agentic-forms-trace";

interface TraceBundle {
  trace: CommonTrace | null;
  rawTrace: RawTrace | null;
}

// Reads any persisted bundle. Guarded for SSR, where sessionStorage is absent.
function load(): TraceBundle {
  if (typeof sessionStorage === "undefined") return { trace: null, rawTrace: null };
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as TraceBundle) : { trace: null, rawTrace: null };
  } catch {
    return { trace: null, rawTrace: null };
  }
}

// A single reactive holder. Components read traceStore.trace and
// traceStore.rawTrace; assigning either is what triggers re-render.
export const traceStore = $state<TraceBundle>(load());

function persist() {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(traceStore));
  } catch {
    // Ignore storage quota or private-mode errors; the in-memory trace still works.
  }
}

// Everything the home page hands over for one turn of the conversation.
export interface RecordTurnInput {
  form: { id: string; name: string | null; sha256: string };
  mapping: MappingRow[];
  branchRules: BranchRule[];
  user: string;
  agentReply: string;
  awaitingInput: boolean;
  model: string;
  // False if the agent call itself did not produce a usable result this turn.
  ok: boolean;
  // The agent's cumulative answers after this turn. Only meaningful when ok
  // is true.
  answers: Record<string, unknown>;
  // The deterministic engine's submit outcome for this turn's answers, used
  // to decide the trace's terminal status once the journey actually closes.
  submitStatus: "submitted" | "blocked";
}

// Records one turn into both the common trace and the raw trace, starting a
// new run first if this is the first turn for the current form.
export function recordTurn(input: RecordTurnInput) {
  const runId = traceStore.trace?.run.id ?? crypto.randomUUID();

  const trace =
    traceStore.trace ??
    startTrace({
      id: runId,
      journeyId: input.form.id,
      implementation: IMPLEMENTATION_AGENT,
      sourceTrace: rawTraceFilename(runId),
      form: input.form,
    });

  const rawTrace = traceStore.rawTrace ?? startRawTrace(runId);

  const contract = { schema: {}, branches: [], mapping: input.mapping, branchRules: input.branchRules };
  const turn = input.ok
    ? ({ ok: true, answers: input.answers } as const)
    : ({ ok: false } as const);

  let nextTrace = appendTurn(trace, contract, turn);

  // The journey closes the first time the agent says it is done. finishJourney
  // is safe to call again on a trace that has already closed, so this does
  // not need to track whether that has already happened.
  if (input.ok && !input.awaitingInput) {
    const status: Exclude<TerminalStatus, "incomplete"> =
      input.submitStatus === "submitted" ? "completed" : "blocked";
    nextTrace = finishJourney(nextTrace, input.answers, status);
  }

  traceStore.trace = nextTrace;
  traceStore.rawTrace = appendRawTurn(rawTrace, {
    user: input.user,
    agentReply: input.agentReply,
    answers: input.ok ? input.answers : {},
    awaitingInput: input.awaitingInput,
    ok: input.ok,
  });

  persist();
}

// Clears the trace. Call when a new form is loaded or the form is reset.
export function resetTrace() {
  traceStore.trace = null;
  traceStore.rawTrace = null;
  persist();
}
