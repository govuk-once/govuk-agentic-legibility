import type { AgentContract, BranchTraceRow } from "./engine-types";

// Renders any answer value into readable text for the branch trace table.
function renderAnswer(value: unknown): string {
  if (value === undefined) return "(not answered)";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    // Serialise nested objects and arrays for readable table cells.
    return JSON.stringify(value);
  } catch {
    return "(unserialisable value)";
  }
}

// Checks whether an answer triggers a given routing rule value.
function answerMatchesRule(answer: unknown, ruleValue: string): boolean {
  if (answer === undefined || answer === null) return false;
  if (Array.isArray(answer)) {
    return answer.map((value) => String(value)).includes(ruleValue);
  }
  if (typeof answer === "object") return false;
  return String(answer) === ruleValue;
}

// Creates a trace row per routing rule so the UI can show branch outcomes.
export function buildBranchTrace(
  contract: AgentContract,
  answers: Record<string, unknown>,
): BranchTraceRow[] {
  return contract.branchRules.map((rule) => {
    const answer = answers[rule.questionKey];
    return {
      questionKey: rule.questionKey,
      questionText: rule.questionText,
      answerValue: rule.answerValue,
      providedAnswer: renderAnswer(answer),
      matched: answerMatchesRule(answer, rule.answerValue),
      jumpTo: rule.jumpTo,
      skippedQuestionTexts: rule.skippedQuestionTexts,
    };
  });
}
