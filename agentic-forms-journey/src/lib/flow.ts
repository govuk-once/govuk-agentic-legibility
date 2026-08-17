// This file lives outside src/lib/server on purpose. It has no dependency
// that needs to stay on the server (no environment variables, no network
// calls), and trace-builder.ts needs to call buildJourneyFlow from code that
// runs in the browser, which SvelteKit will not allow for anything under
// src/lib/server.

import type { AgentContract, MappingRow } from "./server/engine-types";

// Per-run outcome for one question in the LLM journey flow.
// - answered: the question was reached and an answer was provided
// - skipped: an upstream branch routed past this question
// - undetermined: an upstream branch could route past it, but the deciding
//   answer was never provided, so we genuinely cannot say whether it applies
// - unanswered: the question was reached but no answer was provided
export type FlowRunState = "answered" | "skipped" | "undetermined" | "unanswered";

export interface FlowRunStatus {
  state: FlowRunState;
  answer: string | null;
  // For a decision question, the route its answer takes (null when unresolved).
  routeTaken: string | null;
  // True when a human should confirm before this step can be trusted.
  needsHuman: boolean;
  note: string;
}

// One branch rule leaving a decision question.
export interface FlowRoute {
  answerValue: string;
  jumpTo: string;
  skippedQuestionTexts: string[];
}

// One question in the journey, annotated with the agent run's outcome.
export interface FlowNode {
  order: number;
  key: string;
  questionText: string;
  answerType: string;
  required: boolean;
  options: string[];
  isDecision: boolean;
  routes: FlowRoute[];
  status: FlowRunStatus;
}

// Renders any answer value into readable text.
function renderAnswer(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return "(unserialisable value)";
  }
}

// Checks whether an answer satisfies a routing rule value.
function answerMatches(answer: unknown, ruleValue: string): boolean {
  if (answer === undefined || answer === null) return false;
  if (Array.isArray(answer)) return answer.map((value) => String(value)).includes(ruleValue);
  if (typeof answer === "object") return false;
  return String(answer) === ruleValue;
}

// Treats empty strings and empty arrays as "not provided" so blanks do not
// look like real answers in the flow.
function isProvided(answer: unknown): boolean {
  if (answer === undefined || answer === null) return false;
  if (typeof answer === "string") return answer.trim().length > 0;
  if (Array.isArray(answer)) return answer.length > 0;
  return true;
}

// Works out how one question resolves for a single run's answers.
function computeStatus(
  row: MappingRow,
  routes: FlowRoute[],
  answers: Record<string, unknown>,
  contract: AgentContract,
): FlowRunStatus {
  // 1. Would an upstream branch skip this question? Only a rule whose deciding
  //    answer was actually provided can settle that.
  const skippingRules = contract.branchRules.filter((rule) =>
    rule.skippedQuestionTexts.includes(row.questionText),
  );

  let skipNote = "";
  let undeterminedNote = "";
  for (const rule of skippingRules) {
    const decisionAnswer = answers[rule.questionKey];
    if (!isProvided(decisionAnswer)) {
      undeterminedNote = `Route depends on "${rule.questionText}", which was not answered.`;
      continue;
    }
    if (answerMatches(decisionAnswer, rule.answerValue)) {
      skipNote = `Skipped because "${rule.questionText}" was "${rule.answerValue}".`;
      break;
    }
  }

  if (skipNote) {
    return { state: "skipped", answer: null, routeTaken: null, needsHuman: false, note: skipNote };
  }
  if (undeterminedNote) {
    return {
      state: "undetermined",
      answer: null,
      routeTaken: null,
      needsHuman: true,
      note: undeterminedNote,
    };
  }

  // 2. The question is reached. Inspect its own answer.
  const own = answers[row.key];
  const provided = isProvided(own);

  // 3. If it is a decision point, resolve which route the answer takes.
  let routeTaken: string | null = null;
  if (routes.length > 0 && provided) {
    const firing = routes.find((route) => answerMatches(own, route.answerValue));
    routeTaken = firing ? `Jumps to "${firing.jumpTo}"` : "Continues to the next question";
  }

  if (!provided) {
    return {
      state: "unanswered",
      answer: null,
      routeTaken: null,
      needsHuman: row.required || routes.length > 0,
      note:
        routes.length > 0
          ? "Decision answer missing, so the branch it controls cannot be resolved."
          : row.required
            ? "Required answer missing."
            : "Optional answer left blank.",
    };
  }

  return {
    state: "answered",
    answer: renderAnswer(own),
    routeTaken,
    needsHuman: false,
    note: "",
  };
}

// journey structure annotated with the agent run's outcome, so the
// whole branching flow, what the agent answered, and where a human should
// confirm can be read top to bottom. The deterministic run is omitted because
// it always fills every required field.
export function buildJourneyFlow(
  contract: AgentContract,
  answers: Record<string, unknown>,
): FlowNode[] {
  return contract.mapping.map((row, index) => {
    const routes: FlowRoute[] = contract.branchRules
      .filter((rule) => rule.questionKey === row.key)
      .map((rule) => ({
        answerValue: rule.answerValue,
        jumpTo: rule.jumpTo,
        skippedQuestionTexts: rule.skippedQuestionTexts,
      }));

    return {
      order: index + 1,
      key: row.key,
      questionText: row.questionText,
      answerType: row.answerType,
      required: row.required,
      options: row.options ?? [],
      isDecision: routes.length > 0,
      routes,
      status: computeStatus(row, routes, answers, contract),
    };
  });
}
