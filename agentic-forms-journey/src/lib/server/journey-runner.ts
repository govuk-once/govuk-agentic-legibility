import type { GovForm } from "$lib/schemas";
import { buildBranchTrace } from "./branch-trace";
import { runDeterministicFill } from "./deterministic";
import type {
  AgentContract,
  EngineRun,
  FillResult,
  RunMode,
  SubmissionResult,
} from "./engine-types";
import { getMissingRequiredFields, validateAnswers } from "./validation";

// Simulates submit behaviour after validation has completed.
function buildSubmitResult(formId: string, mode: RunMode, valid: boolean): SubmissionResult {
  if (!valid) {
    return {
      status: "blocked",
      reference: null,
      reason: "Answers did not pass validation.",
    };
  }

  return {
    // This is a simulated reference to show submit-stage behaviour in the UI.
    status: "submitted",
    reference: `${formId}-${mode}-reference`,
    reason: "Answers passed validation and were submitted.",
  };
}

// Runs one full journey. The fill stage differs by mode: the deterministic run
// fills its own answers, while the LLM run is handed answers already produced by
// the conversational agent.
export async function runJourney(
  mode: RunMode,
  contract: AgentContract,
  form: GovForm,
  llmFill?: FillResult,
): Promise<EngineRun> {
  const steps: EngineRun["steps"] = [];

  // Stage 1: discover what form we are running and how many pages it contains.
  steps.push({
    stage: "discover",
    status: "success",
    decision: `Read uploaded form ${JSON.stringify(form.name ?? form.id)}`,
    rationale: `Found ${form.pages.length} question(s) in the journey.`,
  });

  // Stage 2: understand the form by building mapping, branches, and schema.
  steps.push({
    stage: "understand",
    status: "success",
    decision: "Built mapping, routing notes, and answer schema",
    rationale: `${contract.mapping.length} mapped key(s), ${contract.branches.length} branch rule(s).`,
  });

  let fillResult: FillResult;
  try {
    // Stage 3: fill answers. This is the only branch point between run modes.
    if (mode === "deterministic") {
      fillResult = runDeterministicFill(contract, form);
    } else if (llmFill) {
      fillResult = llmFill;
    } else {
      throw new Error("No answers were produced for the LLM run.");
    }

    steps.push({
      stage: "fill",
      status: "success",
      decision: fillResult.decision,
      rationale: fillResult.rationale,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown fill error";

    steps.push({
      stage: "fill",
      status: "failed",
      decision: "Could not generate answers",
      rationale: message,
    });

    // If fill fails, later stages are blocked because there are no answers to process.
    steps.push({
      stage: "validate",
      status: "blocked",
      decision: "Validation not run",
      rationale: "Validation depends on answers from the fill stage.",
    });

    steps.push({
      stage: "submit",
      status: "blocked",
      decision: "Submission blocked",
      rationale: "Submission needs a completed fill stage and valid answers.",
    });

    return {
      mode,
      steps,
      answers: {},
      valid: null,
      errors: [],
      missingRequiredFields: [],
      submit: {
        status: "blocked",
        reference: null,
        reason: "Fill stage failed.",
      },
      branchTrace: buildBranchTrace(contract, {}),
      fillError: message,
    };
  }

  const validation = validateAnswers(contract.schema, fillResult.answers);
  const missingRequiredFields = getMissingRequiredFields(validation.errors);

  // Stage 4: validate answers against generated JSON Schema.
  steps.push({
    stage: "validate",
    status: validation.valid ? "success" : "failed",
    decision: validation.valid ? "Validation passed" : "Validation failed",
    rationale: validation.valid
      ? "Answers satisfy the generated schema."
      : `${validation.errors.length} validation issue(s) found.`,
  });

  const submit = buildSubmitResult(form.id, mode, validation.valid);

  // Stage 5: submit only when validation has passed.
  steps.push({
    stage: "submit",
    status: submit.status === "submitted" ? "success" : "blocked",
    decision: submit.status === "submitted" ? "Submission succeeded" : "Submission blocked",
    rationale: submit.reason,
  });

  return {
    mode,
    steps,
    answers: fillResult.answers,
    valid: validation.valid,
    errors: validation.errors,
    missingRequiredFields,
    submit,
    branchTrace: buildBranchTrace(contract, fillResult.answers),
    fillError: null,
  };
}
