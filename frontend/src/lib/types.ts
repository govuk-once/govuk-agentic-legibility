export type JsonPrimitive = string | number | boolean | null;
export type JsonSchemaType = string | string[];
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export interface JsonSchemaProperty {
  type?: JsonSchemaType;
  title?: string;
  description?: string;
  format?: string;
  default?: JsonPrimitive;
  enum?: JsonPrimitive[];
}

export interface JsonSchema {
  type?: JsonSchemaType;
  title?: string;
  description?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  additionalProperties?: boolean;
}

export interface InteractionContent {
  title?: string;
  description?: string;
  data?: unknown;
  [key: string]: unknown;
}

export interface Interaction {
  id?: string;
  content?: InteractionContent;
  input_schema: JsonSchema;
  [key: string]: unknown;
}

export interface JourneyRunResponse {
  run_id: string;
  journey_id: string;
  status: string;
  terminal: boolean;
  interaction: Interaction | null;
  fixture: ConversationFixture | null;
  conversation: ConversationMessage[];
  assistance: AssistanceResponse | null;
  assistance_error: string | null;
}

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface GuidanceReference {
  id: string;
  title: string;
  version: string;
  sha256: string;
}

export interface AssistanceAction {
  type: 'propose_values' | 'no_safe_suggestion' | 'answer_journey_question';
  values: Record<string, JsonPrimitive>;
  message: string | null;
  answer: string | null;
}

export interface AssistanceResponse {
  actions: AssistanceAction[];
  retrieved_guidance: GuidanceReference[];
  model_id: string;
  prompt_id: string;
  duration_ms: number;
}

export interface TraceEvent {
  run_id?: string;
  sequence?: number;
  timestamp?: string;
  type?: string;
  [key: string]: unknown;
}

export interface TraceResponse {
  run_id: string;
  events: TraceEvent[];
}

export interface JourneyHistoryItem {
  sequence: number;
  interactionId: string;
  status: string;
}

export interface ConversationFixture {
  id: string;
  version: string;
  title: string;
  description: string;
  journey_id: string;
  conversation: ConversationMessage[];
}
