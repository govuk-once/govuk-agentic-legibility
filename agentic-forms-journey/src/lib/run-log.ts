// A portable, method-agnostic record of a single agent run.
//
// The point of this file is comparison: this POC emits a RunLog, and other
// agentic-form-filling methods can emit the same shape, so their behaviour can
// be laid side by side on the same criteria. Phase 2 will import several of
// these and diff them. Phase 1 just captures and displays one.
//
// The log is organised around the criteria we want to compare methods on:
//   1. performance: raw time and token cost
//   2. conversationHistory: the full transcript
//   3. interaction: the turn-by-turn back-and-forth
//   4. agentActions: what the agent actually did to the form
//   5. executorActions: reserved; this POC has no executor yet
//
// Everything here is a plain function with no framework or server dependency,
// so it runs on the client (where the conversation lives) and can be unit
// tested in isolation.

import { z } from "zod";

// Identifies which method produced a log, so a comparison view can label it.
export const RUN_LOG_METHOD = "claude-conversational-agent";

// Plain-language explanation of this method, shown on the comparison page so a
// reader knows what they are looking at without prior context.
export const RUN_LOG_DESCRIPTION =
  "An AI agent that reads the form's fields and branching, infers everything it can from a short chat, and asks the citizen only for what it genuinely cannot work out.";

// Bumped when the RunLog shape changes, so importers can detect mismatches.
export const RUN_LOG_VERSION = 1;

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// Raw cost of one agent turn (criterion 1).
export interface PerfTurn {
  turn: number;
  model: string;
  latencyMs: number;
  inputTokens: number;
  outputTokens: number;
}

// One round of the citizen <-> agent exchange (criterion 3).
export interface InteractionTurn {
  turn: number;
  // What the citizen said.
  user: string;
  // What the agent replied.
  agent: string;
  // True when the agent asked the citizen for more information this turn.
  awaitingInput: boolean;
  // Field keys that were filled for the first time on this turn.
  newFields: string[];
}

// What the agent did to a single field (criterion 4). Derived from the journey
// flow's per-question state so it stays in step with the visualisation.
export type AgentActionKind = "filled" | "skipped" | "needs-answer" | "undetermined";

export interface AgentAction {
  field: string;
  questionText: string;
  answerType: string;
  action: AgentActionKind;
  // The value filled, or the reason a field was skipped / left for a human.
  detail: string;
  // True when a person should confirm or supply this before it can be trusted.
  needsHuman: boolean;
}

export interface RunLog {
  schemaVersion: number;
  method: string;
  // Optional human-friendly name for this specific run (e.g. "Parking permit
  // v1"), set when exporting. Used as the display label on the comparison page
  // so runs of the same method can be told apart by something meaningful.
  title?: string;
  // Plain-language explanation of the method (optional so older/other logs load).
  description?: string;
  form: { id: string; name: string | null };
  model: string;
  // Set at export time (client-side), left null while accumulating.
  exportedAt: string | null;
  criteria: {
    // 1. Time / token cost: raw absolute figures, no baseline subtraction.
    performance: {
      totals: {
        turns: number;
        inputTokens: number;
        outputTokens: number;
        totalTokens: number;
        wallMs: number;
      };
      turns: PerfTurn[];
    };
    // 2. Full conversation transcript.
    conversationHistory: ChatMessage[];
    // 3. Turn-by-turn interaction detail.
    interaction: InteractionTurn[];
    // 4. Per-field actions the agent took.
    agentActions: AgentAction[];
    // 5. Executor actions (submitting API calls, etc.). Not available in this
    //    POC: the submit stage is simulated, there is no real executor.
    executorActions: {
      available: boolean;
      note: string;
      actions: unknown[];
    };
  };
}

// Structural shape of a journey-flow node, kept local so this module does not
// import server-only code. Matches the fields buildJourneyFlow produces.
export interface FlowNodeLike {
  key: string;
  questionText: string;
  answerType: string;
  status: {
    state: string;
    answer: string | null;
    needsHuman: boolean;
    note: string;
  };
}

// Everything the client hands over for one recorded turn.
export interface TurnInput {
  form: { id: string; name: string | null };
  // The full transcript after this turn (authoritative history).
  conversation: ChatMessage[];
  // The citizen's message this turn.
  user: string;
  // The agent's reply this turn.
  agentReply: string;
  awaitingInput: boolean;
  telemetry: { model: string; latencyMs: number; inputTokens: number; outputTokens: number };
  // The cumulative journey flow after this turn.
  flow: FlowNodeLike[];
  // Field keys present in the agent's answers after this turn.
  answeredKeys: string[];
}

// A fresh, empty log for a given form.
export function emptyRunLog(form: { id: string; name: string | null }, model: string): RunLog {
  return {
    schemaVersion: RUN_LOG_VERSION,
    method: RUN_LOG_METHOD,
    description: RUN_LOG_DESCRIPTION,
    form,
    model,
    exportedAt: null,
    criteria: {
      performance: {
        totals: { turns: 0, inputTokens: 0, outputTokens: 0, totalTokens: 0, wallMs: 0 },
        turns: [],
      },
      conversationHistory: [],
      interaction: [],
      agentActions: [],
      executorActions: {
        available: false,
        note: "No executor in this POC. The submit stage is simulated, so no real API calls are made.",
        actions: [],
      },
    },
  };
}

// Maps a journey-flow state to the agent action it represents.
function actionFromState(state: string): AgentActionKind {
  switch (state) {
    case "answered":
      return "filled";
    case "skipped":
      return "skipped";
    case "undetermined":
      return "undetermined";
    default:
      return "needs-answer";
  }
}

// Turns the cumulative flow into a per-field action list.
function agentActionsFromFlow(flow: FlowNodeLike[]): AgentAction[] {
  return flow.map((node) => {
    const action = actionFromState(node.status.state);
    const detail =
      action === "filled" && node.status.answer !== null ? node.status.answer : node.status.note;
    return {
      field: node.key,
      questionText: node.questionText,
      answerType: node.answerType,
      action,
      detail,
      needsHuman: node.status.needsHuman,
    };
  });
}

// Appends one turn to a log (creating it if this is the first turn) and returns
// a NEW log object; the input is never mutated, so callers using framework
// reactivity get a fresh reference to assign. The performance turns and
// interaction rows accumulate; the transcript and agent-action list are
// cumulative snapshots, so they are replaced each turn.
export function appendTurn(existing: RunLog | null, input: TurnInput): RunLog {
  const base = existing ?? emptyRunLog(input.form, input.telemetry.model);

  const turn = base.criteria.interaction.length + 1;

  // Field keys that had already been filled before this turn.
  const seen = new Set(base.criteria.interaction.flatMap((row) => row.newFields));
  const newFields = input.answeredKeys.filter((key) => !seen.has(key));

  const perfTurn: PerfTurn = {
    turn,
    model: input.telemetry.model,
    latencyMs: input.telemetry.latencyMs,
    inputTokens: input.telemetry.inputTokens,
    outputTokens: input.telemetry.outputTokens,
  };
  const perfTurns = [...base.criteria.performance.turns, perfTurn];

  const inputTokens = base.criteria.performance.totals.inputTokens + input.telemetry.inputTokens;
  const outputTokens = base.criteria.performance.totals.outputTokens + input.telemetry.outputTokens;

  const interaction: InteractionTurn = {
    turn,
    user: input.user,
    agent: input.agentReply,
    awaitingInput: input.awaitingInput,
    newFields,
  };

  return {
    ...base,
    // Adopt a real model name once we have one (the error fallback reports "unknown").
    model: base.model === "unknown" || base.model === "" ? input.telemetry.model : base.model,
    criteria: {
      ...base.criteria,
      performance: {
        totals: {
          turns: turn,
          inputTokens,
          outputTokens,
          totalTokens: inputTokens + outputTokens,
          wallMs: base.criteria.performance.totals.wallMs + input.telemetry.latencyMs,
        },
        turns: perfTurns,
      },
      conversationHistory: input.conversation,
      interaction: [...base.criteria.interaction, interaction],
      agentActions: agentActionsFromFlow(input.flow),
    },
  };
}

// Runtime schema for a RunLog, used to validate logs imported on the comparison
// page. It must stay in step with the interfaces above; if you change the shape,
// change both. Kept permissive on numbers so logs from other methods are not
// rejected over trivial differences.
const ChatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string(),
});

const PerfTurnSchema = z.object({
  turn: z.number(),
  model: z.string(),
  latencyMs: z.number(),
  inputTokens: z.number(),
  outputTokens: z.number(),
});

const InteractionTurnSchema = z.object({
  turn: z.number(),
  user: z.string(),
  agent: z.string(),
  awaitingInput: z.boolean(),
  newFields: z.array(z.string()),
});

const AgentActionSchema = z.object({
  field: z.string(),
  questionText: z.string(),
  answerType: z.string(),
  action: z.enum(["filled", "skipped", "needs-answer", "undetermined"]),
  detail: z.string(),
  needsHuman: z.boolean(),
});

export const RunLogSchema = z.object({
  schemaVersion: z.number(),
  method: z.string(),
  title: z.string().optional(),
  description: z.string().optional(),
  form: z.object({ id: z.string(), name: z.string().nullable() }),
  model: z.string(),
  exportedAt: z.string().nullable(),
  criteria: z.object({
    performance: z.object({
      totals: z.object({
        turns: z.number(),
        inputTokens: z.number(),
        outputTokens: z.number(),
        totalTokens: z.number(),
        wallMs: z.number(),
      }),
      turns: z.array(PerfTurnSchema),
    }),
    conversationHistory: z.array(ChatMessageSchema),
    interaction: z.array(InteractionTurnSchema),
    agentActions: z.array(AgentActionSchema),
    executorActions: z.object({
      available: z.boolean(),
      note: z.string(),
      actions: z.array(z.unknown()),
    }),
  }),
});

// Validates unknown input (a parsed JSON file) as a RunLog, throwing a ZodError
// with a readable path if it does not conform.
export function parseRunLog(raw: unknown): RunLog {
  return RunLogSchema.parse(raw) as RunLog;
}
