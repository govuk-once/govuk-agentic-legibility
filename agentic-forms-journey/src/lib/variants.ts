// Generates synthetic comparator methods from a REAL run log.
//
// The comparison only works when methods ran the same form. So rather than ship
// fixed "verbose" / "aggressive" methods on a fictional form, we derive them
// from whatever real run the user loads: same form, same field keys, same
// questions, just filled the way a verbose or an over-eager method would.
//
// These are clearly labelled "(synthetic)" so they are never mistaken for real
// runs. A file/upload field is treated as something no method can do on the
// citizen's behalf, so it is always left for a human to fill in.

import type { AgentAction, ChatMessage, RunLog } from "./run-log";

const isFile = (a: AgentAction) => a.answerType === "file";

// Builds the conversation transcript from a set of interaction turns.
function transcript(turns: { user: string; agent: string }[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const t of turns) {
    out.push({ role: "user", content: t.user });
    out.push({ role: "assistant", content: t.agent });
  }
  return out;
}

// The verbose questionnaire: asks one question per field and over-collects,
// filling even the fields a branch would skip. Uploads still need a human.
function verboseFrom(base: RunLog): RunLog {
  const fields = base.criteria.agentActions;

  const agentActions: AgentAction[] = fields.map((f) => ({
    field: f.field,
    questionText: f.questionText,
    answerType: f.answerType,
    action: isFile(f) ? "needs-answer" : "filled",
    detail: isFile(f)
      ? "Upload: the citizen must provide this."
      : "Asked the citizen directly (over-collected, even where a branch made it unnecessary).",
    needsHuman: isFile(f),
  }));

  // One asking turn per non-upload field.
  const askable = fields.filter((f) => !isFile(f));
  const perIn = 1900;
  const perOut = 260;
  const perMs = 2600;

  const interactionCore = askable.map((f, i) => ({
    turn: i + 1,
    user: "(citizen answers)",
    agent: `Please provide: ${f.questionText}`,
    awaitingInput: true,
    newFields: [f.field],
  }));
  // A final turn asking for the uploads, if any.
  const uploads = fields.filter(isFile);
  const interaction =
    uploads.length > 0
      ? [
          ...interactionCore,
          {
            turn: interactionCore.length + 1,
            user: "(citizen answers)",
            agent: `Please upload: ${uploads.map((u) => u.questionText).join(", ")}`,
            awaitingInput: true,
            newFields: [] as string[],
          },
        ]
      : interactionCore;

  const perfTurns = interaction.map((t) => ({
    turn: t.turn,
    model: "synthetic-verbose",
    latencyMs: perMs,
    inputTokens: perIn,
    outputTokens: perOut,
  }));
  const nTurns = perfTurns.length;

  return {
    schemaVersion: 1,
    method: "verbose questionnaire (synthetic)",
    description:
      "Synthetic comparator, generated from this form. Asks one question per field instead of inferring, and over-collects fields a branch would have skipped.",
    form: base.form,
    model: "synthetic-verbose",
    exportedAt: null,
    criteria: {
      performance: {
        totals: {
          turns: nTurns,
          inputTokens: perIn * nTurns,
          outputTokens: perOut * nTurns,
          totalTokens: (perIn + perOut) * nTurns,
          wallMs: perMs * nTurns,
        },
        turns: perfTurns,
      },
      conversationHistory: transcript(interaction),
      interaction,
      agentActions,
      executorActions: { available: false, note: "Synthetic, no executor.", actions: [] },
    },
  };
}

// The aggressive auto-filler: fills everything in one pass by guessing, asks
// nothing, and flags every guess for a human to confirm. Branch-skipped fields
// stay skipped; uploads are left for a human.
function aggressiveFrom(base: RunLog): RunLog {
  const fields = base.criteria.agentActions;

  const agentActions: AgentAction[] = fields.map((f) => {
    if (f.action === "skipped") {
      return { ...f, detail: "Skipped (assumed branch).", needsHuman: false };
    }
    if (isFile(f)) {
      return {
        field: f.field,
        questionText: f.questionText,
        answerType: f.answerType,
        action: "needs-answer",
        detail: "Upload: the citizen must provide this.",
        needsHuman: true,
      };
    }
    return {
      field: f.field,
      questionText: f.questionText,
      answerType: f.answerType,
      action: "filled",
      detail: "Guessed in a single pass (unconfirmed).",
      needsHuman: true,
    };
  });

  const filledFields = agentActions.filter((a) => a.action === "filled").map((a) => a.field);

  const interaction = [
    {
      turn: 1,
      user: "(one request)",
      agent: "Filled everything I could guess. Please review the details before submitting.",
      awaitingInput: false,
      newFields: filledFields,
    },
  ];

  return {
    schemaVersion: 1,
    method: "aggressive autofill (synthetic)",
    description:
      "Synthetic comparator, generated from this form. Fills every field in one pass by guessing, asks nothing, and flags every guess for a human to confirm.",
    form: base.form,
    model: "synthetic-autofill",
    exportedAt: null,
    criteria: {
      performance: {
        totals: { turns: 1, inputTokens: 1800, outputTokens: 320, totalTokens: 2120, wallMs: 2000 },
        turns: [{ turn: 1, model: "synthetic-autofill", latencyMs: 2000, inputTokens: 1800, outputTokens: 320 }],
      },
      conversationHistory: transcript(interaction),
      interaction,
      agentActions,
      executorActions: { available: false, note: "Synthetic, no executor.", actions: [] },
    },
  };
}

// Produces verbose + aggressive comparators for the given real run, on the same
// form so they can be compared against it directly.
export function deriveComparators(base: RunLog): RunLog[] {
  return [verboseFrom(base), aggressiveFrom(base)];
}
