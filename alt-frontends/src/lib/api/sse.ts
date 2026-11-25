import { getApiBaseUrl } from '$lib/api/client';
import type { RunEvent } from '$lib/types';

/**
 * Subscribes to `GET /runs/{id}/events`. Each connection replays the run's
 * full transcript from the start (see agent/api/events.py:watch_run — it
 * always begins diffing from index 0), so no separate initial state fetch
 * is needed to populate history.
 */
export function watchRun(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError?: (error: Event) => void
): () => void {
  const url = `${getApiBaseUrl()}/api/v1/runs/${encodeURIComponent(runId)}/events`;
  const source = new EventSource(url);

  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as RunEvent);
    } catch {
      // Ignore malformed payloads rather than tearing down the stream.
    }
  };

  if (onError) {
    source.onerror = onError;
  }

  return () => source.close();
}
