const BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

export interface FormSummary {
  id: number | string;
  name?: string;
  slug?: string;
}

export interface StartSessionResponse {
  session_id: string;
  form_id: string;
  form_name: string;
  temporal_workflow_id: string;
  policy: string;
}

export interface SessionState {
  session_id: string;
  workflow_id: string;
  status: string;
  awaiting: AwaitingInput | null;
  presentation: Presentation | null;
  form_metadata: FormMetadata;
  policy: string;
  auto_answered: AutoAnswered[];
  pending_proposal: Proposal | null;
}

export interface AwaitingInput {
  token: string;
  prompt: string;
  schema: InputSchema;
  options?: Option[] | null;
  timeout_seconds?: number | null;
  state_id?: string | null;
  state_type?: string | null;
}

export interface InputSchema {
  kind: "string" | "boolean" | "select_one" | "select_many" | "file_ref";
  options?: Option[];
  allow_skip?: boolean;
  default?: any;
  presentation?: Presentation;
}

export interface Option {
  value: string;
  label: string;
}

export interface Presentation {
  source: string;
  step_id: string;
  position: number;
  question_text: string;
  page_heading: string | null;
  hint_text: string | null;
  guidance_markdown: string | null;
  answer_type: string;
  answer_settings: Record<string, any>;
  is_optional: boolean;
  field: string | null;
  field_label: string | null;
  required: boolean;
  is_first_field: boolean;
}

export interface FormMetadata {
  form_id: string;
  name: string;
  form_slug: string;
  support_url: string | null;
  support_email: string | null;
  support_phone: string | null;
  support_url_text: string | null;
  language: string;
  what_happens_next_markdown: string | null;
  privacy_policy_url: string | null;
  declaration_markdown: string | null;
  submission_type: string;
}

export interface AutoAnswered {
  state_id: string;
  question_text: string;
  submitted_value: any;
  explanation: string;
}

export interface Proposal {
  has_answer: boolean;
  value: any;
  explanation: string;
  token?: string;
  state_id?: string;
  question_text?: string;
  requires_confirmation?: boolean;
}

export async function listForms(): Promise<FormSummary[]> {
  return request<FormSummary[]>("/api/forms");
}

export async function startSession(
  formId: string | number,
  policy: string = "manual"
): Promise<StartSessionResponse> {
  return request<StartSessionResponse>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ form_id: String(formId), policy }),
  });
}

export async function getSessionState(
  sessionId: string
): Promise<SessionState> {
  return request<SessionState>(`/api/sessions/${sessionId}/state`);
}

export async function submitAnswer(
  sessionId: string,
  token: string,
  value: any
): Promise<any> {
  return request(`/api/sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ token, value }),
  });
}

export async function sendChat(
  sessionId: string,
  message: string
): Promise<{ response: string; state: any }> {
  return request(`/api/sessions/${sessionId}/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function requestProposal(
  sessionId: string
): Promise<Proposal> {
  return request<Proposal>(`/api/sessions/${sessionId}/propose`, {
    method: "POST",
  });
}

export async function confirmProposal(sessionId: string): Promise<any> {
  return request(`/api/sessions/${sessionId}/confirm-proposal`, {
    method: "POST",
  });
}

export async function rejectProposal(sessionId: string): Promise<any> {
  return request(`/api/sessions/${sessionId}/reject-proposal`, {
    method: "POST",
  });
}

export async function setPolicy(
  sessionId: string,
  policy: string
): Promise<any> {
  return request(`/api/sessions/${sessionId}/policy`, {
    method: "PUT",
    body: JSON.stringify({ policy }),
  });
}
