// The common trace format agreed with legibility team to apply across prototypes where possible.
//
// Each prototype can keep its own detailed raw trace of what happened inside
// it. The common trace is a smaller, shared account of what happens: which questions became available, what values were proposed and
// submitted, and how the run ended.
//
// Field names are consistent with the naming convention detailed in common trace RFC 12.8.26

import { z } from "zod";

// Changed only when the shared specification itself changes shape.
export const SCHEMA_VERSION = "0.1";

// Each way this app can produce a run gets its own implementation name, since
// the point of the common trace is to compare approaches, not just runs. The
// live agent is named after its role (agent) rather than a specific model, so
// the name still makes sense if the underlying model changes later.
export const IMPLEMENTATION_AGENT = "agentic-forms-journey-agent";
export const IMPLEMENTATION_DETERMINISTIC = "agentic-forms-journey-deterministic";
export const IMPLEMENTATION_VERBOSE_SYNTHETIC = "agentic-forms-journey-verbose-synthetic";
export const IMPLEMENTATION_AGGRESSIVE_SYNTHETIC = "agentic-forms-journey-aggressive-synthetic";

// The terminal outcome of a run, reusing the same words the submit stage
// already uses elsewhere in this app. A run that has not reached an outcome
// yet (the conversation is still going) is incomplete rather than failed.
export type TerminalStatus = "completed" | "blocked" | "incomplete";

// The service made an interaction available to the user, for example a
// question the form can now show because an earlier branch resolved to it.
export interface InteractionAvailableEvent {
  type: "interaction_available";
  interaction_id: string;
}

// Values were proposed for an interaction. In this app that means the agent
// worked out, or was told, an answer to a question.
export interface ValuesProposedEvent {
  type: "values_proposed";
  interaction_id: string;
  values: Record<string, unknown>;
}

// An answer was presented to the user, as opposed to the agent simply
// asking for more information. Kept narrow for now: this app mostly asks
// questions rather than answering them, so this event is only used for the
// final confirmation message. It could be expanded upon, or the context of
// what we interpret as an AnswerPresented event may change in the future.
export interface AnswerPresentedEvent {
  type: "answer_presented";
  interaction_id?: string;
}

// Values were submitted to the service as final. This app has no separate
// review step, so submission happens once, when the journey finishes, using
// whichever values survived to that point.
export interface ValuesSubmittedEvent {
  type: "values_submitted";
  interaction_id: string;
  values: Record<string, unknown>;
}

// The app tried to get agent assistance for a turn but could not produce a
// usable result, for example the model call failed. This is a whole turn
// failing, not one field, so it carries no interaction_id.
export interface AssistanceFailedEvent {
  type: "assistance_failed";
}

// The journey reached a terminal outcome. This fires once per run, the first
// time the conversation actually concludes, not on every turn.
export interface JourneyFinishedEvent {
  type: "journey_finished";
  status: TerminalStatus;
  result: Record<string, unknown>;
}

export type TraceEvent =
  | InteractionAvailableEvent
  | ValuesProposedEvent
  | AnswerPresentedEvent
  | ValuesSubmittedEvent
  | AssistanceFailedEvent
  | JourneyFinishedEvent;

export interface CommonTrace {
  schema_version: typeof SCHEMA_VERSION;
  // Points to the raw trace file this common trace was derived from, or null
  // if no raw trace has been produced for this run.
  source_trace: string | null;
  run: {
    id: string;
    // The form or service journey this run went through.
    journey_id: string;
    implementation: string;
    status: TerminalStatus;
  };
  // What the run started from. For this app, the fixed starting point is the
  // uploaded form rather than a scripted conversation or service structure/schema with a list of API endpoints, so this points to the
  // form instead of a conversation fixture.
  initial_context?: {
    form: { id: string; name: string | null; sha256: string };
  };
  events: TraceEvent[];
}

// Runtime shape used to validate a common trace file on the way in, so an
// imported file that does not match the shared format gets a clear error
// instead of breaking the comparison page silently.
const InteractionAvailableSchema = z.object({
  type: z.literal("interaction_available"),
  interaction_id: z.string(),
});

const ValuesProposedSchema = z.object({
  type: z.literal("values_proposed"),
  interaction_id: z.string(),
  values: z.record(z.string(), z.unknown()),
});

const AnswerPresentedSchema = z.object({
  type: z.literal("answer_presented"),
  interaction_id: z.string().optional(),
});

const ValuesSubmittedSchema = z.object({
  type: z.literal("values_submitted"),
  interaction_id: z.string(),
  values: z.record(z.string(), z.unknown()),
});

const AssistanceFailedSchema = z.object({
  type: z.literal("assistance_failed"),
});

const TerminalStatusSchema = z.enum(["completed", "blocked", "incomplete"]);

const JourneyFinishedSchema = z.object({
  type: z.literal("journey_finished"),
  status: TerminalStatusSchema,
  result: z.record(z.string(), z.unknown()),
});

const TraceEventSchema = z.discriminatedUnion("type", [
  InteractionAvailableSchema,
  ValuesProposedSchema,
  AnswerPresentedSchema,
  ValuesSubmittedSchema,
  AssistanceFailedSchema,
  JourneyFinishedSchema,
]);

export const CommonTraceSchema = z.object({
  schema_version: z.literal(SCHEMA_VERSION),
  source_trace: z.string().nullable(),
  run: z.object({
    id: z.string(),
    journey_id: z.string(),
    implementation: z.string(),
    status: TerminalStatusSchema,
  }),
  initial_context: z
    .object({
      form: z.object({
        id: z.string(),
        name: z.string().nullable(),
        sha256: z.string(),
      }),
    })
    .optional(),
  events: z.array(TraceEventSchema),
});

// Checks that unknown input, such as an imported JSON file, is a valid common
// trace. Throws a readable error if it does not match the shared format.
export function parseCommonTrace(raw: unknown): CommonTrace {
  return CommonTraceSchema.parse(raw) as CommonTrace;
}
