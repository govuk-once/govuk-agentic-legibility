import { z } from "zod";

// Allowed answer types from the GOV Forms payload we accept.
export const AnswerTypeSchema = z.enum([
  "text",
  "number",
  "date",
  "email",
  "phone_number",
  "national_insurance_number",
  "address",
  "name",
  "organisation_name",
  "selection",
  "file",
]);

// Validates uploaded GOV Forms JSON before any mapping or agent logic runs.
// This is the input contract for the whole pipeline.
export const GovFormSchema = z.object({
  // Form identifier from GOV Forms export.
  id: z.string(),
  // Human-readable form name, when present.
  name: z.string().optional(),

  // Ordered list of question pages.
  pages: z
    .array(
      z.object({
        // Stable page identifier used in routing links.
        id: z.string(),
        // GOV Forms position, if present. We fall back to array order when missing.
        position: z.number().optional(),
        questionText: z.string(),
        hintText: z.string().optional(),

        // Optional questions are not added to top-level required list by default.
        isOptional: z.boolean().default(false),
        answerType: AnswerTypeSchema,

        // Additional settings vary by answer type (for example selection options).
        answerSettings: z
          .object({
            inputType: z.enum(["single_line", "long_text"]).optional(),
            selectionType: z.enum(["radio", "checkbox"]).optional(),
            selectionOptions: z.array(z.object({ name: z.string() })).optional(),
            includeTitle: z.boolean().optional(),
          })
          .optional(),

        // Forward routing rules ("if answer X then jump to page Y").
        routing: z
          .array(
            z.object({
              answerValue: z.string(),
              goToPageId: z.string(),
            }),
          )
          .optional(),
      }),
    )
    .min(1),
});

export type GovForm = z.infer<typeof GovFormSchema>;

// These are the stages shown in the journey timeline.
export const StageNameSchema = z.enum([
  "discover",
  "understand",
  "fill",
  "validate",
  "submit",
]);

// Stage status is used to show whether each stage succeeded, failed, or was blocked.
export const StageStatusSchema = z.enum(["success", "failed", "blocked"]);

// One timeline row for either the deterministic run or the LLM run.
export const AgentStepSchema = z.object({
  // Canonical stage name so both runs are compared stage by stage.
  stage: StageNameSchema,

  // Stage outcome shown in timeline dots and tables.
  status: StageStatusSchema,

  // Short summary of what happened in this stage.
  decision: z.string(),

  // Extra context shown to help explain why that outcome happened.
  rationale: z.string(),
});

export type AgentStep = z.infer<typeof AgentStepSchema>;

// Validates the agent's conversational output each turn.
// The model supplies its best-effort answers plus the reply shown to the citizen.
export const LlmChatSchema = z.object({
  // Best-effort answer payload keyed by mapped field keys.
  final_answers: z.record(z.string(), z.unknown()),

  // Natural-language message shown to the citizen (asks for the minimum missing
  // information, or confirms the form is complete).
  reply: z.string(),

  // True when the agent still needs more information from the citizen.
  awaiting_input: z.boolean().optional().default(false),
});

export type LlmChat = z.infer<typeof LlmChatSchema>;
