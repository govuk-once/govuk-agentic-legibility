import { env } from '$env/dynamic/public';
import type {
  ConversationFixture,
  JourneyRunResponse,
  TraceResponse
} from '$lib/types';

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8001';

export class JourneyApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
    this.name = 'JourneyApiError';
  }
}

export function getApiBaseUrl(): string {
  return (env.PUBLIC_JOURNEY_API_URL || DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function getConversationFixtures(): Promise<ConversationFixture[]> {
  return request<ConversationFixture[]>('/api/conversation-fixtures');
}

export async function startJourney(
  journeyId: string,
  fixtureId: string | null
): Promise<JourneyRunResponse> {
  return request<JourneyRunResponse>('/api/journey-runs', {
    method: 'POST',
    body: JSON.stringify({ journey_id: journeyId, fixture_id: fixtureId })
  });
}

export async function submitJourneyResult(
  runId: string,
  result: Record<string, unknown>
): Promise<JourneyRunResponse> {
  return request<JourneyRunResponse>(`/api/journey-runs/${encodeURIComponent(runId)}/results`, {
    method: 'POST',
    body: JSON.stringify({ result })
  });
}

export async function addJourneyMessage(
  runId: string,
  content: string
): Promise<JourneyRunResponse> {
  return request<JourneyRunResponse>(
    `/api/journey-runs/${encodeURIComponent(runId)}/messages`,
    {
      method: 'POST',
      body: JSON.stringify({ content })
    }
  );
}

export async function getJourneyTrace(runId: string): Promise<TraceResponse> {
  return request<TraceResponse>(`/api/journey-runs/${encodeURIComponent(runId)}/trace`);
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
    throw new JourneyApiError(`Could not reach the journey executor API: ${detail}`, 0);
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new JourneyApiError(errorDetail(payload, response.statusText), response.status);
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
  return fallback || 'Journey executor request failed';
}
