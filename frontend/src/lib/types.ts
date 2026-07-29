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
