import type { RunEvent } from '$lib/types';
import { cleanTextPipes } from '$lib/server/agent/clean-text';
import { getOptionsFromState } from '$lib/server/agent/options-from-state';
import { runs, runState } from './engine';

// Port of durable_poc/agent/api/events.py:watch_run over the in-memory store:
// replays the transcript from the start, then emits diffs until the run ends.

const POLL_INTERVAL_MS = 500;
const TERMINAL_STATUSES = new Set(['COMPLETED', 'FAILED', 'TERMINATED']);

export function watchRunStream(runId: string, signal: AbortSignal): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let lastSeenIndex = 0;
  const handledTokens = new Set<string>();
  let timer: ReturnType<typeof setTimeout> | null = null;

  return new ReadableStream({
    start(controller) {
      const send = (event: RunEvent) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      const close = () => {
        if (timer) clearTimeout(timer);
        try {
          controller.close();
        } catch {
          // already closed by the client disconnecting
        }
      };
      signal.addEventListener('abort', close);

      const poll = () => {
        if (signal.aborted) return;
        const run = runs.get(runId);
        if (!run) {
          // Like the real stream, keep polling an unknown id rather than erroring.
          timer = setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }
        const state = runState(run);
        const { transcript, awaiting } = state;

        for (let idx = lastSeenIndex; idx < transcript.length; idx++) {
          const cleanMsg = cleanTextPipes(transcript[idx].message ?? '');
          if (cleanMsg.startsWith('[ENGINE LOG]')) {
            send({ type: 'trace', category: 'ENGINE', summary: 'FSM Execution Event', detail: cleanMsg.replace('[ENGINE LOG]', '').trim() });
          } else {
            send({ type: 'message', role: 'assistant', text: cleanMsg });
            send({ type: 'trace', category: 'ENGINE', summary: 'OutputState Transcript Emitted', detail: cleanMsg });
          }
        }
        lastSeenIndex = Math.max(lastSeenIndex, transcript.length);

        const token = awaiting?.token;
        if (awaiting && token && !handledTokens.has(token)) {
          handledTokens.add(token);
          const cleanPrompt = cleanTextPipes(awaiting.prompt ?? '');
          if (cleanPrompt) {
            send({ type: 'message', role: 'assistant', text: cleanPrompt });
            send({
              type: 'trace',
              category: 'ENGINE',
              summary: `Awaiting InputState [${token}]`,
              detail: { prompt: cleanPrompt, schema: awaiting.schema }
            });
          }
          const opts = getOptionsFromState(state);
          send({ type: 'options', kind: opts.kind, options: opts.options });
          if (awaiting.timeout_seconds !== null && awaiting.timeout_seconds !== undefined) {
            send({ type: 'timeout', seconds: awaiting.timeout_seconds });
          }
        }

        if (!awaiting && TERMINAL_STATUSES.has(state.status)) {
          send({ type: 'completed', status: state.status });
          close();
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      };
      poll();
    },
    cancel() {
      if (timer) clearTimeout(timer);
    }
  });
}
