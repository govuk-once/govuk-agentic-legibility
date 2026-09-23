const BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch { /* Keep the server's original error text. */ }
    throw new Error(detail || `API error ${res.status}`);
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
  review_before_submit: boolean;
}

export interface SessionState {
  session_id: string;
  workflow_id: string;
  status: string;
  awaiting: AwaitingInput | null;
  presentation: Presentation | null;
  form_metadata: FormMetadata;
  policy: string;
  upload_mode?: "mock" | "local";
  auto_answered: AutoAnswered[];
  answered_count: number;
  answer_history: AcceptedAnswer[];
  review_before_submit: boolean;
  review_required: boolean;
  review_confirmed: boolean;
  review_ready: boolean;
  review_revision: number;
  review_replay_needs_input: boolean;
  pending_proposal: Proposal | null;
  transcript?: Array<{ message: string }>;
  result?: { status: string; outcome?: string } | null;
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
  exclusive_options?: string[];
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

export interface AcceptedAnswer {
  state_id: string;
  question_text: string;
  value: any;
  schema: InputSchema;
  presentation: Presentation | null;
  source: "auto" | "manual" | "confirm";
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
  steps_taken?: number;
}

export interface ConversationFixture {
  id: string;
  title: string;
  description: string;
  form_id: string | null;
  message_count: number;
}

export interface ConversationFixtureDetail extends ConversationFixture {
  conversation: Array<{ role: string; content: string }>;
}

export async function listForms(): Promise<FormSummary[]> {
  return request<FormSummary[]>("/api/forms");
}

export async function listFixtures(): Promise<ConversationFixture[]> {
  return request<ConversationFixture[]>("/api/fixtures");
}

export async function getFixture(
  fixtureId: string
): Promise<ConversationFixtureDetail> {
  return request<ConversationFixtureDetail>(`/api/fixtures/${fixtureId}`);
}

export async function startSession(
  formId: string | number,
  policy: string = "manual",
  fixtureId?: string | null,
  reviewBeforeSubmit: boolean = false
): Promise<StartSessionResponse> {
  return request<StartSessionResponse>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      form_id: String(formId),
      policy,
      fixture_id: fixtureId || null,
      review_before_submit: reviewBeforeSubmit,
    }),
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

export async function uploadFile(
  sessionId: string, token: string, file: File, mode: "mock" | "local" = "mock"
): Promise<{ ref: string; bytes: number; content_type: string; mock?: boolean }> {
  const path = `/api/sessions/${sessionId}/files?token=${encodeURIComponent(token)}`;
  if (mode === "mock") {
    // Preview mode NEVER transmits the File object or reads its contents.
    // The server issues a session/token-bound reference to allow progression.
    return request<{ ref: string; bytes: number; content_type: string; mock: boolean }>(
      `/api/sessions/${sessionId}/files/mock?token=${encodeURIComponent(token)}`, {
      method: "POST",
      body: JSON.stringify({ bytes: file.size, content_type: file.type || "application/octet-stream" }),
    });
  }
  // Explicitly opt-in local development mode, for synthetic files only.
  const response = await fetch(path, {
    method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file,
  });
  if (!response.ok) throw new Error(`Upload failed (${response.status}): ${await response.text()}`);
  return response.json();
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
  policy: string,
  reviewBeforeSubmit?: boolean
): Promise<any> {
  return request<{ policy: string; review_before_submit: boolean }>(`/api/sessions/${sessionId}/policy`, {
    method: "PUT",
    body: JSON.stringify({ policy, review_before_submit: reviewBeforeSubmit }),
  });
}

export async function amendReview(
  sessionId: string, index: number, stateId: string, value: any, revision: number
): Promise<SessionState> {
  return request<SessionState>(`/api/sessions/${sessionId}/review/amend`, {
    method: "POST",
    body: JSON.stringify({ index, state_id: stateId, value, revision }),
  });
}

export async function confirmReview(sessionId: string): Promise<{ review_confirmed: boolean }> {
  return request(`/api/sessions/${sessionId}/review/confirm`, { method: "POST" });
}

export interface AutoProgressEvent {
  type: "step" | "waiting" | "done";
  question?: string;
  value?: string;
  explanation?: string;
  reason?: "needs_input" | "needs_upload" | "complete" | "pending" | "error" | "max_steps" | "policy_changed";
  step?: number;
  steps_taken?: number;
  answered_count?: number;
  total_questions?: number;
}

export function streamAutoProgress(
  sessionId: string,
  onEvent: (event: AutoProgressEvent) => void,
  onError?: (error: any) => void
): { close: () => void } {
  const source = new EventSource(`${BASE}/api/sessions/${sessionId}/auto-progress`);

  function handleMessage(eventType: string) {
    return (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as AutoProgressEvent;
        onEvent(data);
        if (data.type === "done") {
          source.close();
        }
      } catch (err) {
        onError?.(err);
      }
    };
  }

  source.addEventListener("step", handleMessage("step"));
  source.addEventListener("waiting", handleMessage("waiting"));
  source.addEventListener("done", handleMessage("done"));

  source.onerror = (e) => {
    onError?.(e);
    source.close();
  };

  return {
    close: () => source.close(),
  };
}
