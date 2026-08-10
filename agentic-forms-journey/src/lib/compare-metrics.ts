// Pure helpers that turn a set of RunLogs into the numbers and rows the
// comparison page renders. No framework or server dependency; everything is
// derived from the logs themselves, so the comparison never needs the original
// form or an API call.
//
// Framing: one method is the REFERENCE (a baseline, typically the deterministic
// full journey) and the others are CANDIDATES measured against it. Cost metrics
// (tokens, wall time) are only ranked among methods that actually used an LLM,
// because a rule-based method trivially wins on cost and that comparison is noise.

import type { AgentActionKind, RunLog } from "./run-log";

// One method loaded into the comparison. `id` is a unique key (methods that
// share a name across different forms must still be distinguishable); `label` is
// the human-facing name, which does NOT need to be globally unique because only
// one form's methods are shown at a time.
export interface Method {
  id: string;
  label: string;
  log: RunLog;
}

// A set of methods that all ran the same form: the unit within which a fair
// comparison can be drawn.
export interface FormGroup {
  formId: string;
  formName: string | null;
  methods: Method[];
}

// Groups loaded methods by the form they ran, largest group first. Methods can
// only be compared within a group, because comparing across different forms
// (different questions/branching) is not like-for-like.
export function groupByForm(methods: Method[]): FormGroup[] {
  const groups = new Map<string, FormGroup>();
  for (const method of methods) {
    const id = method.log.form.id;
    let group = groups.get(id);
    if (!group) {
      group = { formId: id, formName: method.log.form.name, methods: [] };
      groups.set(id, group);
    }
    group.methods.push(method);
  }
  return [...groups.values()].sort((a, b) => b.methods.length - a.methods.length);
}

// True when a method actually spent tokens (i.e. used an LLM). Rule-based
// baselines report zero and are excluded from cost rankings.
export function usesLlm(log: RunLog): boolean {
  return log.criteria.performance.totals.totalTokens > 0;
}

// Chooses a sensible default reference (returns its id): prefer a zero-cost
// (deterministic) baseline if one is loaded, otherwise the first method.
export function defaultReference(methods: Method[]): string | null {
  if (methods.length === 0) return null;
  const baseline = methods.find((m) => !usesLlm(m.log));
  return (baseline ?? methods[0]).id;
}

// Scorecard figures for a single method.
export interface MethodMetrics {
  usesLlm: boolean;
  turns: number;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  wallMs: number;
  questionsAsked: number;
  fieldsFilled: number;
  // Filled by the agent but flagged for a human to CONFIRM before submitting.
  fieldsToConfirm: number;
  fieldsSkipped: number;
  // Not filled by the agent; left for a human to FILL IN (e.g. an upload, or a
  // required answer it could not work out). Optional fields left blank do not count.
  fieldsToFillByHuman: number;
  executorActions: number | null; // null when the method has no executor
}

export function methodMetrics(log: RunLog): MethodMetrics {
  const actions = log.criteria.agentActions;
  const count = (kind: AgentActionKind) => actions.filter((a) => a.action === kind).length;
  const totals = log.criteria.performance.totals;

  return {
    usesLlm: usesLlm(log),
    turns: totals.turns,
    inputTokens: totals.inputTokens,
    outputTokens: totals.outputTokens,
    totalTokens: totals.totalTokens,
    wallMs: totals.wallMs,
    questionsAsked: log.criteria.interaction.filter((t) => t.awaitingInput).length,
    fieldsFilled: count("filled"),
    fieldsToConfirm: actions.filter((a) => a.action === "filled" && a.needsHuman).length,
    fieldsSkipped: count("skipped"),
    fieldsToFillByHuman: actions.filter((a) => a.action !== "filled" && a.needsHuman).length,
    executorActions: log.criteria.executorActions.available
      ? log.criteria.executorActions.actions.length
      : null,
  };
}

// A scorecard row: one metric across every method.
export interface ScorecardRow {
  group: string;
  label: string;
  values: (number | null)[];
  display: string[];
  better: "lower" | "higher" | null;
  bestIndexes: number[];
  // True for cost rows: only agentic methods are ranked, and non-agentic cells
  // are shown as "instant by design" rather than as competitors.
  agenticOnly: boolean;
}

export interface Scorecard {
  rows: ScorecardRow[];
  // Aligned to the methods array: whether each method used an LLM.
  agenticFlags: boolean[];
}

function ms(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
  return `${Math.round(value)}ms`;
}

// Works out which method(s) win a row. `eligible` restricts ranking to a subset
// (used for cost rows). Ties and all-equal rows produce no winner.
function bestIndexes(
  values: (number | null)[],
  better: "lower" | "higher" | null,
  eligible?: boolean[],
): number[] {
  if (!better) return [];
  const entries = values
    .map((v, i) => ({ v, i }))
    .filter((e): e is { v: number; i: number } => e.v !== null && (!eligible || eligible[e.i]));
  if (entries.length < 2) return [];
  const nums = entries.map((e) => e.v);
  const target = better === "lower" ? Math.min(...nums) : Math.max(...nums);
  if (nums.every((n) => n === target)) return [];
  return entries.filter((e) => e.v === target).map((e) => e.i);
}

export function buildScorecard(methods: Method[]): Scorecard {
  const metrics = methods.map((m) => methodMetrics(m.log));
  const agenticFlags = metrics.map((m) => m.usesLlm);

  const row = (
    group: string,
    label: string,
    pick: (m: MethodMetrics) => number | null,
    better: "lower" | "higher" | null,
    opts: { agenticOnly?: boolean; format?: (v: number) => string } = {},
  ): ScorecardRow => {
    const values = metrics.map(pick);
    const agenticOnly = opts.agenticOnly ?? false;
    const format = opts.format ?? String;
    return {
      group,
      label,
      values,
      display: values.map((v, i) => {
        if (v === null) return "n/a";
        if (agenticOnly && !agenticFlags[i]) return "instant"; // rule-based, no LLM cost
        return format(v);
      }),
      better,
      agenticOnly,
      bestIndexes: bestIndexes(values, better, agenticOnly ? agenticFlags : undefined),
    };
  };

  return {
    agenticFlags,
    rows: [
      // Behavioural (fair to compare across all methods).
      row("Interaction", "Conversation turns", (m) => m.turns, "lower"),
      row("Interaction", "Questions asked of the human", (m) => m.questionsAsked, "lower"),
      // Cost (only meaningful between agentic methods).
      row("Cost (agentic only)", "Input tokens", (m) => m.inputTokens, "lower", {
        agenticOnly: true,
        format: (v) => v.toLocaleString(),
      }),
      row("Cost (agentic only)", "Output tokens", (m) => m.outputTokens, "lower", {
        agenticOnly: true,
        format: (v) => v.toLocaleString(),
      }),
      row("Cost (agentic only)", "Total tokens", (m) => m.totalTokens, "lower", {
        agenticOnly: true,
        format: (v) => v.toLocaleString(),
      }),
      row("Cost (agentic only)", "Wall time", (m) => m.wallMs, "lower", {
        agenticOnly: true,
        format: ms,
      }),
      // Coverage / outcome.
      row("Agent actions", "Fields filled", (m) => m.fieldsFilled, null),
      row("Agent actions", "Filled but needs a human to confirm", (m) => m.fieldsToConfirm, "lower"),
      row("Agent actions", "Skipped via branch", (m) => m.fieldsSkipped, null),
      row("Agent actions", "Left for a human to fill in", (m) => m.fieldsToFillByHuman, "lower"),
      row("Executor", "API submissions", (m) => m.executorActions, null),
    ],
  };
}

// One candidate method's treatment of a question, relative to the reference.
export interface DivergenceCandidate {
  id: string;
  label: string;
  action: AgentActionKind | null;
  detail: string | null;
  needsHuman: boolean;
  // Differs from the reference if the action kind differs, OR one filled a value
  // a human must still confirm while the other did not.
  differs: boolean;
}

// One field's treatment: the reference's handling plus each candidate's.
export interface DivergenceRow {
  field: string;
  questionText: string;
  reference: AgentActionKind | null;
  referenceDetail: string | null;
  referenceNeedsHuman: boolean;
  candidates: DivergenceCandidate[];
  diverges: boolean; // at least one candidate differs from the reference
}

export interface Divergence {
  formId: string;
  formName: string | null;
  referenceLabel: string;
  // Candidate column headers (id is a stable, unique key for rendering).
  candidateColumns: { id: string; label: string }[];
  // Candidates dropped because they ran a different form from the reference.
  excludedLabels: string[];
  rows: DivergenceRow[];
}

// Per-question divergence is measured against the REFERENCE method (by id), and
// only across candidates that ran the same form as the reference.
export function buildDivergence(methods: Method[], referenceId: string | null): Divergence | null {
  if (methods.length < 2) return null;

  const reference = methods.find((m) => m.id === referenceId) ?? methods[0];
  const formId = reference.log.form.id;

  const others = methods.filter((m) => m.id !== reference.id);
  const candidates = others.filter((m) => m.log.form.id === formId);
  const excluded = others.filter((m) => m.log.form.id !== formId);
  if (candidates.length < 1) return null;

  // Field order: reference first, then any fields only candidates saw.
  const order: string[] = [];
  const questionText = new Map<string, string>();
  const register = (m: Method) => {
    for (const action of m.log.criteria.agentActions) {
      if (!questionText.has(action.field)) {
        order.push(action.field);
        questionText.set(action.field, action.questionText);
      }
    }
  };
  register(reference);
  candidates.forEach(register);

  const actionFor = (m: Method, field: string) =>
    m.log.criteria.agentActions.find((a) => a.field === field) ?? null;

  const rows: DivergenceRow[] = order.map((field) => {
    const refAction = actionFor(reference, field);
    const refKind = refAction ? refAction.action : null;
    const refHuman = refAction ? refAction.needsHuman : false;

    const candidateCells = candidates.map((c) => {
      const found = actionFor(c, field);
      const kind = found ? found.action : null;
      const human = found ? found.needsHuman : false;
      return {
        id: c.id,
        label: c.label,
        action: kind,
        detail: found ? found.detail : null,
        needsHuman: human,
        differs: kind !== refKind || human !== refHuman,
      };
    });
    return {
      field,
      questionText: questionText.get(field) ?? field,
      reference: refKind,
      referenceDetail: refAction ? refAction.detail : null,
      referenceNeedsHuman: refHuman,
      candidates: candidateCells,
      diverges: candidateCells.some((c) => c.differs),
    };
  });

  return {
    formId,
    formName: reference.log.form.name,
    referenceLabel: reference.label,
    candidateColumns: candidates.map((c) => ({ id: c.id, label: c.label })),
    excludedLabels: excluded.map((c) => c.label),
    rows,
  };
}
