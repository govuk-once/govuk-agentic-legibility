import type { AgentStep } from "$lib/schemas";

// Loose JSON Schema shape used for generated schema objects.
export type JsonSchema = Record<string, unknown>;

// Two execution modes that share one common stage pipeline.
export type RunMode = "deterministic" | "llm";

// One mapping row linking a GOV question page to an agent-facing key.
export interface MappingRow {
  pageId: string;
  key: string;
  questionText: string;
  answerType: string;
  required: boolean;
  appliesWhen?: string;
  options?: string[];
}

// One explicit routing rule used for branch trace visualisation.
export interface BranchRule {
  questionKey: string;
  questionText: string;
  answerValue: string;
  jumpTo: string;
  skippedQuestionTexts: string[];
}

// Shared contract used by both deterministic and LLM journey runs.
export interface AgentContract {
  schema: JsonSchema;
  mapping: MappingRow[];
  branches: string[];
  branchRules: BranchRule[];
}

// Standardised validation output from Ajv.
export interface ValidationResult {
  valid: boolean;
  errors: { field: string; message: string }[];
}

// Submit stage output (submitted when valid, blocked when invalid).
export interface SubmissionResult {
  status: "submitted" | "blocked";
  reference: string | null;
  reason: string;
}

// One row in the branch trace table.
export interface BranchTraceRow {
  questionKey: string;
  questionText: string;
  answerValue: string;
  providedAnswer: string;
  matched: boolean;
  jumpTo: string;
  skippedQuestionTexts: string[];
}

// Fill-stage output shape before validate/submit stages run.
export interface FillResult {
  answers: Record<string, unknown>;
  decision: string;
  rationale: string;
}

// One turn in the user and agent conversation.
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// Fill output plus the agent's chat reply for the conversational flow.
export interface ChatFillResult extends FillResult {
  // Natural-language message shown to the user.
  reply: string;
  // True when the agent still needs something before the form can be submitted.
  awaitingInput: boolean;
  // Model that produced this turn, kept for reference even though this app
  // does not track cost or timing.
  model: string;
}

// Full output for one run mode across all canonical stages.
export interface EngineRun {
  mode: RunMode;
  steps: AgentStep[];
  answers: Record<string, unknown>;
  valid: boolean | null;
  errors: { field: string; message: string }[];
  missingRequiredFields: string[];
  submit: SubmissionResult;
  branchTrace: BranchTraceRow[];
  fillError: string | null;
}
