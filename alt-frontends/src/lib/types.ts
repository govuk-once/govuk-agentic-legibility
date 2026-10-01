// Mirrors durable_poc/src/context.py + src/model.py's wire shapes (via
// agent/tools.py's _to_dict), not a JSON-Schema. `awaiting.schema.kind`
// drives which KindField variant renders the current field.

export interface SchemaDefinition {
  kind: string;
  pattern?: string | null;
  normalise?: string | null;
  max_length?: number | null;
  invalid_message?: string | null;
  options?: Array<{ value: string; label: string } | string | Record<string, unknown>> | null;
  options_from?: string | null;
  value_key?: string | null;
  label_key?: string | null;
  values?: string[] | null;
  labels?: Record<string, string> | null;
  default?: unknown;
  accept?: string[] | null;
  allow_skip?: boolean | null;
}

export interface AwaitingInput {
  token: string;
  prompt: string;
  schema: SchemaDefinition;
  options?: unknown;
  timeout_seconds?: number | null;
  state_id?: string | null;
  state_type?: string | null;
}

export interface TranscriptEntry {
  step: number;
  timestamp: string;
  message: string;
}

export interface RunStateDTO {
  workflow_id: string;
  status: string;
  awaiting: AwaitingInput | null;
  transcript: TranscriptEntry[];
}

export interface WorkflowSummary {
  id: string;
  name?: string;
  [key: string]: unknown;
}

// `GET /runs/{id}/events` (SSE) payload shapes — see agent/api/events.py:RunEvent.
// `escalation` is only ever emitted by the autonomous `/agentic` resume stream
// (`POST /runs/{id}/autonomy/resume`), not the plain `GET /runs/{id}/events` feed.
export type RunEvent =
  | { type: 'message'; role?: string; text?: string }
  | { type: 'trace'; category?: string; summary?: string; detail?: unknown }
  | { type: 'options'; kind?: string | null; options?: string[] }
  | { type: 'timeout'; seconds?: number }
  | { type: 'completed'; status?: string }
  | {
      type: 'escalation';
      category?: string;
      summary?: string;
      detail?: {
        reason?: string;
        token?: string;
        prompt?: string;
        schema?: SchemaDefinition;
        [key: string]: unknown;
      };
    };

// Mirrors agent/api/schemas.py:AutonomyPolicy.
export interface AutonomyPolicy {
  autonomy_level: 'cautious' | 'balanced' | 'assertive';
  notify_categories: string[];
  pause_before_external_call: boolean;
}

// Mirrors agent/api/schemas.py:SetAutonomyRequest.
export interface SetAutonomyRequest {
  policy: AutonomyPolicy;
  /** Evaluation scenario to seed from; '' for none (pre-seeded facts only). */
  profile_fixture: string;
  /** Free-text facts the user gives up front, before the run is driven. */
  preseed?: string;
}

// `GET /api/v1/profiles` entries — see agent/api/routes/agentic.py:list_profiles.
export interface ProfileSummary {
  fixture: string;
  title: string;
  journey_id: string;
}

export interface ActiveWorkflowSummary {
  id: string;
  status: string;
}

// `/api/web/[workflowId]/prefill` response, when a suggestion is available.
export interface PrefillSuggestion {
  value: unknown;
  confidence: 'high' | 'medium' | 'low';
  reason: string;
}
