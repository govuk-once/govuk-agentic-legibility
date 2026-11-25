import { env } from '$env/dynamic/public';
import type {
  AwaitingInput,
  PrefillSuggestion,
  ProfileSummary,
  RunEvent,
  RunStateDTO,
  SetAutonomyRequest,
  WorkflowSummary
} from '$lib/types';
import type { WorkflowDefinition } from '$lib/graph/fsm';

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8010';

export class DurableApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
    this.name = 'DurableApiError';
  }
}

export function getApiBaseUrl(): string {
  return (env.PUBLIC_DURABLE_API_URL || DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function listWorkflows(): Promise<WorkflowSummary[]> {
  return request<WorkflowSummary[]>('/api/v1/workflows');
}

export async function getWorkflowDefinition(workflowId: string): Promise<WorkflowDefinition> {
  return request<WorkflowDefinition>(`/api/v1/workflows/${encodeURIComponent(workflowId)}`);
}

export async function startRun(workflowId: string): Promise<{ workflow_id: string }> {
  return request<{ workflow_id: string }>('/api/v1/runs', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId })
  });
}

export async function listActiveRuns(): Promise<Array<{ id: string; status: string }>> {
  return request<Array<{ id: string; status: string }>>('/api/v1/runs');
}

export async function getRunState(runId: string): Promise<RunStateDTO> {
  return request<RunStateDTO>(`/api/v1/runs/${encodeURIComponent(runId)}`);
}

export async function submitRunInput(
  runId: string,
  token: string,
  value: unknown
): Promise<RunStateDTO> {
  return request<RunStateDTO>(`/api/v1/runs/${encodeURIComponent(runId)}/input`, {
    method: 'POST',
    body: JSON.stringify({ token, value })
  });
}

export async function listProfiles(): Promise<ProfileSummary[]> {
  return request<ProfileSummary[]>('/api/v1/profiles');
}

// `/api/web/{id}/context` and `/api/web/{id}/prefill` are SvelteKit's own
// routes (src/routes/api/web/...), same-origin like the agentic autonomy
// routes above — the opt-in notes and any LLM call both live in this app's
// backend, never in durable_poc.
export async function saveWebContext(workflowId: string, context: string): Promise<void> {
  const response = await fetch(`/api/web/${encodeURIComponent(workflowId)}/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ context })
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }
}

export async function getPrefillSuggestion(
  workflowId: string,
  awaiting: AwaitingInput
): Promise<PrefillSuggestion | null> {
  const response = await fetch(`/api/web/${encodeURIComponent(workflowId)}/prefill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ awaiting })
  });
  if (!response.ok) {
    return null;
  }
  const payload = (await response.json().catch(() => null)) as { suggestion: PrefillSuggestion | null } | null;
  return payload?.suggestion ?? null;
}

// `/api/agentic/{id}/autonomy` and `/api/agentic/{id}/autonomy/resume` are
// SvelteKit's own routes (src/routes/api/agentic/...), not durable_poc's —
// LLM interactions run in this app's backend, so these are same-origin, not
// built from `getApiBaseUrl()`.
export async function setAutonomy(
  workflowId: string,
  body: SetAutonomyRequest
): Promise<{ workflow_id: string; policy: SetAutonomyRequest['policy']; profile_fixture: string }> {
  const response = await fetch(`/api/agentic/${encodeURIComponent(workflowId)}/autonomy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }
  return payload as { workflow_id: string; policy: SetAutonomyRequest['policy']; profile_fixture: string };
}

/** The run's saved autonomy config, or null if none has been set. */
export async function getAutonomy(workflowId: string): Promise<(SetAutonomyRequest & { workflow_id: string }) | null> {
  const response = await fetch(`/api/agentic/${encodeURIComponent(workflowId)}/autonomy`);
  if (response.status === 404) return null;
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }
  return payload as SetAutonomyRequest & { workflow_id: string };
}

// Both `resumeAutonomy` and `sendChatMessage` POST to a SvelteKit route that
// streams Server-Sent Events, but SSE only has a GET-based `EventSource` API
// — this reads the streamed response body by hand instead, splitting on the
// same blank-line-delimited "data: ..." framing `sse.ts`'s EventSource
// wrapper gets for free from the browser.
async function readSseBody(response: Response, onEvent: (event: RunEvent) => void): Promise<void> {
  if (!response.body) return;
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;

    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const dataLine = rawEvent.split('\n').find((line) => line.startsWith('data: '));
      if (dataLine) {
        onEvent(JSON.parse(dataLine.slice('data: '.length)) as RunEvent);
      }
      boundary = buffer.indexOf('\n\n');
    }
  }
}

export async function resumeAutonomy(
  workflowId: string,
  onEvent: (event: RunEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`/api/agentic/${encodeURIComponent(workflowId)}/autonomy/resume`, {
      method: 'POST',
      signal
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Unknown network error';
    throw new DurableApiError(`Could not reach the autonomy resume endpoint: ${detail}`, 0);
  }

  if (!response.ok || !response.body) {
    const payload: unknown = await response.json().catch(() => null);
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }

  await readSseBody(response, onEvent);
}

// Replaces WS /chat. `action: 'resume'` mirrors the WS's `{action: 'resume',
// workflow_id}` message — synchronous, no LLM turn, so it is a plain POST
// rather than an SSE stream.
export async function resumeChatSession(
  conversationId: string,
  workflowId: string
): Promise<{ workflowId: string; state: RunStateDTO; options: { kind: string | null; options: string[] } }> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversationId, action: 'resume', workflowId })
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }
  return payload as {
    workflowId: string;
    state: RunStateDTO;
    options: { kind: string | null; options: string[] };
  };
}

export async function sendChatMessage(
  conversationId: string,
  message: string,
  onEvent: (event: RunEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  let response: Response;
  try {
    response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversationId, message }),
      signal
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Unknown network error';
    throw new DurableApiError(`Could not reach the chat endpoint: ${detail}`, 0);
  }

  if (!response.ok || !response.body) {
    const payload: unknown = await response.json().catch(() => null);
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }

  await readSseBody(response, onEvent);
}

// `/api/voice/transcribe` and `/api/voice/speak` are SvelteKit's own routes
// wrapping AWS Transcribe Streaming / Polly — same-origin, binary bodies
// rather than JSON, so they bypass the SSE/JSON helpers above.
export async function transcribeAudio(pcmBuffer: ArrayBuffer): Promise<string> {
  let response: Response;
  try {
    response = await fetch('/api/voice/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: pcmBuffer
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Unknown network error';
    throw new DurableApiError(`Could not reach the transcription endpoint: ${detail}`, 0);
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }
  return (payload as { transcript: string }).transcript;
}

export async function synthesizeSpeech(text: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch('/api/voice/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Unknown network error';
    throw new DurableApiError(`Could not reach the speech endpoint: ${detail}`, 0);
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }
  return response.blob();
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init.headers
      }
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Unknown network error';
    throw new DurableApiError(`Could not reach the durable workflow API: ${detail}`, 0);
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DurableApiError(errorDetail(payload, response.statusText), response.status);
  }
  return payload as T;
}

function errorDetail(payload: unknown, fallback: string): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === 'string') {
      return detail;
    }
    return JSON.stringify(detail);
  }
  return fallback || 'Durable workflow API request failed';
}
