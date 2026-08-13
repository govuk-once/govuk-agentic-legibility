// The raw trace for one run: the full detail behind a common trace.
//
// The common trace deliberately leaves out the exact words used in the
// conversation. This file is where that detail still lives, so a person can
// read exactly what was said and what the agent produced on each turn. It
// does not hold time or token cost: this app is not measuring performance,
// so nothing here should carry that either.
//
// This file has no knock on effects of its own, matching trace-builder.ts. It
// does not create a run id or read the clock. Whatever code runs the
// conversation supplies the run id and tells this module what happened on
// each turn.

// One turn of the conversation, kept in full.
export interface RawTraceTurn {
  turn: number;
  user: string;
  agentReply: string;
  // The agent's answers after this turn. Empty when the turn failed.
  answers: Record<string, unknown>;
  awaitingInput: boolean;
  // False if the agent call itself did not produce a usable result this turn.
  ok: boolean;
}

export interface RawTrace {
  runId: string;
  turns: RawTraceTurn[];
}

// Starts a new, empty raw trace for one run. Call this once, before the
// first turn.
export function startRawTrace(runId: string): RawTrace {
  return { runId, turns: [] };
}

// Adds one turn to the raw trace. Returns a new trace; the one passed in is
// never changed.
export function appendRawTurn(trace: RawTrace, turn: Omit<RawTraceTurn, "turn">): RawTrace {
  return { ...trace, turns: [...trace.turns, { ...turn, turn: trace.turns.length + 1 }] };
}

// Renders the raw trace as JSON Lines, one JSON object per turn. This is the
// file format the shared specification itself expects a raw trace to be in,
// and is what a common trace's source_trace field points to.
export function toJsonl(trace: RawTrace): string {
  return trace.turns.map((turn) => JSON.stringify(turn)).join("\n");
}

// The filename a raw trace is exported and referenced under, built from the
// run id so a common trace's source_trace always matches the file a reader
// would actually download.
export function rawTraceFilename(runId: string): string {
  return `raw-trace-${runId}.jsonl`;
}
