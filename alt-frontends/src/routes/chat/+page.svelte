<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { DurableApiError, listActiveRuns, resumeChatSession, sendChatMessage } from '$lib/api/client';
  import { watchRun } from '$lib/api/sse';
  import RunPicker from '$lib/components/RunPicker.svelte';
  import TranscriptView from '$lib/components/TranscriptView.svelte';
  import TraceSidebar from '$lib/components/TraceSidebar.svelte';
  import type { ActiveWorkflowSummary, RunEvent } from '$lib/types';

  interface TranscriptLine {
    role: string;
    text: string;
  }

  interface TraceLine {
    category: string;
    summary: string;
    detail?: unknown;
  }

  // Client-generated: chat sessions are keyed by conversation, not by
  // workflowId, since the workflowId is unknown until partway through a
  // conversation (see $lib/server/agent/conversation-store.ts).
  const conversationId = crypto.randomUUID();

  let transcript: TranscriptLine[] = $state([]);
  let traces: TraceLine[] = $state([]);
  let activeWorkflows: ActiveWorkflowSummary[] = $state([]);
  let options: string[] = $state([]);
  let optionsKind: string | null = $state(null);
  let selectedMulti: Set<string> = $state(new Set());
  let timeoutSeconds: number | null = $state(null);
  let status: string | null = $state(null);
  let draft = $state('');
  let sending = $state(false);
  let error: string | null = $state(null);

  let workflowId: string | null = null;
  let stopWatching: (() => void) | null = null;

  // Passive background updates (engine trace, timeouts, completion) run
  // decoupled from user-driven turns, exactly like /web and /agentic —
  // direct browser -> durable_poc SSE, unrelated to the LLM turn itself.
  function startWatching(id: string) {
    if (workflowId === id && stopWatching) return;
    stopWatching?.();
    workflowId = id;
    stopWatching = watchRun(id, handleEvent);
  }

  function handleEvent(event: RunEvent) {
    if (event.type === 'message' && event.text) {
      transcript = [...transcript, { role: event.role ?? 'assistant', text: event.text }];
    } else if (event.type === 'trace') {
      if (
        event.category === 'SYSTEM' &&
        event.summary === 'Active Workflow' &&
        typeof event.detail === 'string'
      ) {
        startWatching(event.detail);
      }
      traces = [
        ...traces,
        { category: event.category ?? 'ENGINE', summary: event.summary ?? '', detail: event.detail }
      ];
    } else if (event.type === 'options') {
      optionsKind = event.kind ?? null;
      options = event.options ?? [];
      selectedMulti = new Set();
    } else if (event.type === 'timeout') {
      timeoutSeconds = event.seconds ?? null;
    } else if (event.type === 'completed') {
      status = event.status ?? 'COMPLETED';
      options = [];
    }
  }

  onMount(async () => {
    try {
      activeWorkflows = await listActiveRuns();
    } catch {
      // Non-fatal: the resume picker just stays empty.
    }
  });

  async function sendText(text: string) {
    if (!text.trim() || sending) return;
    transcript = [...transcript, { role: 'user', text }];
    draft = '';
    options = [];
    sending = true;
    error = null;
    try {
      await sendChatMessage(conversationId, text, handleEvent);
    } catch (err) {
      error = err instanceof DurableApiError ? err.message : 'Failed to send message';
    } finally {
      sending = false;
    }
  }

  function submitDraft() {
    sendText(draft);
  }

  function chooseOption(option: string) {
    sendText(option);
  }

  function toggleMultiOption(option: string) {
    if (selectedMulti.has(option)) {
      selectedMulti.delete(option);
    } else {
      selectedMulti.add(option);
    }
    selectedMulti = new Set(selectedMulti);
  }

  function confirmMultiSelection() {
    if (selectedMulti.size === 0) return;
    sendText(Array.from(selectedMulti).join(', '));
  }

  async function resume(id: string) {
    status = null;
    transcript = [];
    traces = [];
    options = [];
    error = null;
    try {
      const { workflowId: resumedId, state, options: opts } = await resumeChatSession(
        conversationId,
        id
      );
      startWatching(resumedId);
      optionsKind = opts.kind;
      options = opts.options;
      if (state.status && state.status !== 'RUNNING') {
        status = state.status;
      }
    } catch (err) {
      error = err instanceof DurableApiError ? err.message : 'Failed to resume run';
    }
  }

  onDestroy(() => stopWatching?.());
</script>

<div class="chat-layout">
  <aside class="chat-layout__runs">
    <RunPicker workflows={activeWorkflows} onresume={resume} />
  </aside>

  <div class="chat-layout__main">
<h1 class="govuk-heading-l">Chat</h1>

{#if error}
  <p class="govuk-error-message">{error}</p>
{/if}

<TranscriptView lines={transcript} />

{#if timeoutSeconds}
  <p class="govuk-body"><strong>Please respond within {Math.ceil(timeoutSeconds / 60)} minute(s).</strong></p>
{/if}

{#if status}
  <p class="govuk-body">Workflow completed (status: {status}).</p>
{/if}

{#if options.length > 0}
  <div class="govuk-!-margin-bottom-4">
    {#if optionsKind === 'select_many'}
      {#each options as option (option)}
        <button
          type="button"
          class="govuk-button govuk-button--secondary govuk-!-margin-right-2"
          aria-pressed={selectedMulti.has(option)}
          onclick={() => toggleMultiOption(option)}
        >
          {option}{selectedMulti.has(option) ? ' ✓' : ''}
        </button>
      {/each}
      <button type="button" class="govuk-button" onclick={confirmMultiSelection}>
        Confirm selections
      </button>
    {:else}
      {#each options as option (option)}
        <button
          type="button"
          class="govuk-button govuk-button--secondary govuk-!-margin-right-2"
          onclick={() => chooseOption(option)}
        >
          {option}
        </button>
      {/each}
    {/if}
  </div>
{/if}

<form
  class="govuk-!-margin-bottom-6"
  onsubmit={(event) => {
    event.preventDefault();
    submitDraft();
  }}
>
  <div class="govuk-form-group">
    <label class="govuk-label" for="chat-input">Message</label>
    <input
      class="govuk-input"
      id="chat-input"
      type="text"
      bind:value={draft}
      disabled={!!status || sending}
    />
  </div>
  <button class="govuk-button" type="submit" disabled={!!status || sending}>Send</button>
</form>
  </div>

  <aside class="chat-layout__trace">
    <TraceSidebar {traces} />
  </aside>
</div>

<style>
  /* Three columns (runs, chat, trace) that run the full width of the window, with the dividers
     meeting the header. The page sits inside a 960px container that also has a gap under the
     header, so both are undone here for this route only. */
  .chat-layout {
    display: flex;
    flex-direction: column;
    margin: -25px calc(50% - 50vw) 0;
    min-height: calc(100vh - 67px);
  }

  .chat-layout__runs,
  .chat-layout__trace {
    box-sizing: border-box;
    padding: 24px 20px;
    border-bottom: 1px solid #b1b4b6;
  }

  .chat-layout__main {
    flex: 1 1 auto;
    padding: 24px 20px;
  }

  @media (min-width: 40.0625em) {
    .chat-layout {
      margin-top: -40px;
    }
  }

  @media (min-width: 64em) {
    .chat-layout {
      flex-direction: row;
    }

    .chat-layout__runs,
    .chat-layout__trace {
      flex: 0 0 auto;
      border-bottom: 0;
    }

    .chat-layout__runs {
      width: 300px;
      border-right: 1px solid #b1b4b6;
    }

    .chat-layout__trace {
      width: 340px;
      border-left: 1px solid #b1b4b6;
    }

    .chat-layout__main {
      padding: 24px 40px;
    }
  }
</style>
