// Runs a /mvi02 call. With the agent on, it answers what it can from the facts and hands each
// question it can't answer to the caller. With the agent off, every question goes to the caller.

import { browser } from '$app/environment';
// Shared (src/lib/api/client.ts): run state, the journey definition, answers, and the agent's resume loop
import {
  DurableApiError,
  getRunState,
  getWorkflowDefinition,
  resumeAutonomy,
  submitRunInput
} from '$lib/api/client';
// Shared (src/lib/api/sse.ts): live events for the run
import { watchRun } from '$lib/api/sse';
// Shared (src/lib/types.ts): the question, event and schema types
import type { AwaitingInput, RunEvent, SchemaDefinition } from '$lib/types';
// Shared (src/lib/mvi/format.ts): journey names and text tidying
import { describeWorkflow, tidyClosingMessage, tidyText } from '$lib/mvi/format';
import type { AnswerSource, ReviewItem } from './answers';

export type Phase = 'connecting' | 'paused' | 'working' | 'asking' | 'ended';

export class CallController {
  readonly runId: string;
  readonly agent: boolean;
  readonly autorun: boolean;

  phase = $state<Phase>('connecting');
  /** The question waiting for the caller. */
  awaiting = $state<AwaitingInput | null>(null);
  answers = $state<ReviewItem[]>([]);
  error = $state<string | null>(null);
  submitting = $state(false);
  department = $state('');
  journey = $state('');
  elapsed = $state(0);
  closingMessages = $state<string[]>([]);
  /** Every question seen on the run, by token, so the agent's answers can be shown with their question. */
  prompts = $state<Record<string, { prompt: string; schema: SchemaDefinition }>>({});

  #stopWatching: (() => void) | null = null;
  #abort: AbortController | null = null;
  #timer: ReturnType<typeof setInterval> | null = null;
  #startedAt = Date.now();

  constructor(runId: string, agent: boolean, autorun: boolean) {
    this.runId = runId;
    this.agent = agent;
    this.autorun = autorun;
  }

  /** Starts listening to the run. Called once, in the browser. */
  start() {
    if (!browser) return;

    this.#stopWatching = watchRun(this.runId, (event) => this.#onRunEvent(event));
    this.#timer = setInterval(() => {
      this.elapsed = Math.floor((Date.now() - this.#startedAt) / 1000);
    }, 1000);

    getWorkflowDefinition(this.runId)
      .then((definition) => {
        const described = describeWorkflow(definition.id);
        this.department = described.department;
        this.journey = described.journey;
      })
      .catch(() => {
        // The call still works without the department and journey names.
      });

    if (this.agent) {
      if (this.autorun) void this.resume();
      else this.phase = 'paused';
    }
  }

  destroy() {
    this.#stopWatching?.();
    this.#abort?.abort();
    if (this.#timer) clearInterval(this.#timer);
  }

  /** Lets the agent carry on, until it finishes or needs the caller. */
  async resume() {
    if (this.#abort) return;
    this.error = null;
    this.awaiting = null;
    this.phase = 'working';
    this.#abort = new AbortController();
    try {
      await resumeAutonomy(this.runId, (event) => this.#onAgentEvent(event), this.#abort.signal);
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        this.error = error instanceof DurableApiError ? error.message : 'The agent could not carry on.';
      }
    } finally {
      this.#abort = null;
      // The stream ended without asking a question or finishing, so offer to try again.
      if (this.phase === 'working') {
        this.phase = 'paused';
        this.error ??= 'The agent stopped before it finished.';
      }
    }
  }

  /** Sends the caller's answer. Returns whether it was accepted. */
  async submit(value: unknown, display: string, source: AnswerSource): Promise<boolean> {
    const awaiting = this.awaiting;
    if (!awaiting || this.submitting) return false;
    this.submitting = true;
    this.error = null;
    try {
      await submitRunInput(this.runId, awaiting.token, value);
      this.answers = [...this.answers, { token: awaiting.token, value, source, display }];
      this.awaiting = null;
      if (this.agent) void this.resume();
      else this.phase = 'working';
      return true;
    } catch (error) {
      this.error = error instanceof DurableApiError ? error.message : 'Failed to send your answer';
      return false;
    } finally {
      this.submitting = false;
    }
  }

  #onRunEvent(event: RunEvent) {
    if (event.type === 'trace' && event.summary?.startsWith('Awaiting InputState [')) {
      const token = /\[(.+?)\]/.exec(event.summary)?.[1];
      const detail = event.detail as { prompt?: string; schema?: SchemaDefinition } | undefined;
      if (token && detail?.prompt) {
        this.prompts[token] = { prompt: tidyText(detail.prompt), schema: detail.schema ?? { kind: 'string' } };
      }
    } else if (event.type === 'options' && !this.agent) {
      void this.#refreshAwaiting();
    } else if (event.type === 'completed') {
      void this.#finish();
    }
  }

  #onAgentEvent(event: RunEvent) {
    if (event.type === 'trace') {
      if (event.category === 'AGENT' && event.summary?.startsWith('Autonomously resolved field')) {
        const detail = event.detail as { token?: string; value?: unknown } | undefined;
        if (detail?.token) {
          this.answers = [...this.answers, { token: detail.token, value: detail.value, source: 'facts' }];
        }
      } else if (event.summary === 'Autonomous step failed') {
        this.error = typeof event.detail === 'string' ? event.detail : 'The agent could not finish a step.';
      }
    } else if (event.type === 'escalation') {
      const detail = event.detail;
      this.#ask({
        token: detail?.token ?? '',
        prompt: tidyText(detail?.prompt ?? 'Please answer'),
        schema: detail?.schema ?? { kind: 'string' }
      });
    } else if (event.type === 'completed') {
      void this.#finish();
    }
  }

  /** Puts a question in front of the caller, and remembers it for the review. */
  #ask(awaiting: AwaitingInput) {
    this.prompts[awaiting.token] ??= { prompt: awaiting.prompt, schema: awaiting.schema };
    this.awaiting = awaiting;
    this.phase = 'asking';
  }

  async #refreshAwaiting() {
    try {
      const state = await getRunState(this.runId);
      if (state.awaiting) {
        this.#ask({ ...state.awaiting, prompt: tidyText(state.awaiting.prompt) });
      } else if (state.status !== 'RUNNING') {
        await this.#finish();
      }
    } catch (error) {
      this.error = error instanceof DurableApiError ? error.message : 'Failed to load the call';
    }
  }

  async #finish() {
    if (this.phase === 'ended') return;
    this.phase = 'ended';
    this.awaiting = null;
    if (this.#timer) clearInterval(this.#timer);
    this.#stopWatching?.();
    this.#abort?.abort();
    try {
      const state = await getRunState(this.runId);
      this.closingMessages = state.transcript
        .map((entry) => tidyText(entry.message ?? ''))
        .filter((message) => message !== '' && !message.startsWith('[ENGINE LOG]'))
        .map(tidyClosingMessage)
        .filter((message) => message !== '');
    } catch {
      // The screen still shows without the closing messages.
    }
  }
}
