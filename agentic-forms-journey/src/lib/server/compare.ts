import type { GovForm } from "$lib/schemas";
import { buildAgentContract } from "./contract-builder";
import type { ChatMessage } from "./engine-types";
import { buildJourneyFlow } from "../flow";
import { runJourney } from "./journey-runner";
import { runLlmChat } from "./llm";

// Calculates how many deterministic keys are also present in the LLM answer payload.
function calculateAnswerOverlap(
  deterministicAnswers: Record<string, unknown>,
  llmAnswers: Record<string, unknown>,
): number {
  const deterministicKeys = new Set(Object.keys(deterministicAnswers));
  if (deterministicKeys.size === 0) return 0;

  const llmKeys = new Set(Object.keys(llmAnswers));
  const overlapCount = [...deterministicKeys].filter((key) => llmKeys.has(key)).length;
  return Number((overlapCount / deterministicKeys.size).toFixed(2));
}

// Runs the deterministic baseline and one agent turn over the conversation, then
// compares outcomes. The agent's reply is surfaced for the chat interface.
export async function runComparison(form: GovForm, messages: ChatMessage[]) {
  // Build once and reuse across both run modes so comparison stays like-for-like.
  const contract = buildAgentContract(form);

  // Deterministic baseline fills every required field on its own.
  const deterministic = await runJourney("deterministic", contract, form);

  // The agent reads the whole conversation and produces answers plus a reply.
  // A failure here should not blank the page, so it falls back to a spoken
  // error. llmOk tells the caller plainly whether this turn actually worked,
  // rather than leaving it to guess from the wording of decision.
  let chat;
  let llmOk = true;
  try {
    chat = await runLlmChat(contract, messages);
  } catch (error) {
    llmOk = false;
    const message = error instanceof Error ? error.message : "Unknown error";
    chat = {
      answers: {},
      reply: `Sorry, I couldn't process that just now (${message}). Please try again.`,
      awaitingInput: true,
      decision: "Agent error",
      rationale: message,
      model: "unknown",
    };
  }

  const llm = await runJourney("llm", contract, form, {
    answers: chat.answers,
    decision: chat.decision,
    rationale: chat.rationale,
  });

  const answerOverlap = calculateAnswerOverlap(deterministic.answers, llm.answers);

  return {
    form: { id: form.id, name: form.name ?? null },
    mapping: contract.mapping,
    branches: contract.branches,
    branchRules: contract.branchRules,
    flow: buildJourneyFlow(contract, llm.answers),
    deterministic,
    llm,
    reply: chat.reply,
    awaitingInput: chat.awaitingInput,
    model: chat.model,
    // True unless the agent call itself failed this turn.
    llmOk,
    compare: {
      detValid: deterministic.valid,
      llmValid: llm.valid,
      detValidationErrorCount: deterministic.errors.length,
      llmValidationErrorCount: llm.valid === null ? null : llm.errors.length,
      detMissingRequiredFields: deterministic.missingRequiredFields,
      llmMissingRequiredFields: llm.valid === null ? null : llm.missingRequiredFields,
      detSubmitStatus: deterministic.submit.status,
      llmSubmitStatus: llm.submit.status,
      answerOverlap,
    },
  };
}
