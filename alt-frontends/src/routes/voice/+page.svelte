<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import {
    DurableApiError,
    listActiveRuns,
    resumeChatSession,
    sendChatMessage,
    synthesizeSpeech,
    transcribeAudio
  } from '$lib/api/client';
  import { watchRun } from '$lib/api/sse';
  import { startPcmRecording, type PcmRecording } from '$lib/audio/pcm-recorder';
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

  // Voice reuses /chat's exact turn pipeline (same conversationId/session
  // keying, same RunEvent vocabulary) with an audio codec layer wrapped
  // around it, per durable_poc/agent/api/routes/chat_ws.py's own docstring.
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

  let recording = $state(false);
  let voiceStatus: string | null = $state(null);
  let micError: string | null = $state(null);
  let activeRecorder: PcmRecording | null = null;

  let workflowId: string | null = null;
  let stopWatching: (() => void) | null = null;

  function startWatching(id: string) {
    if (workflowId === id && stopWatching) return;
    stopWatching?.();
    workflowId = id;
    stopWatching = watchRun(id, handleEvent);
  }

  async function speak(text: string) {
    try {
      voiceStatus = 'Speaking…';
      const blob = await synthesizeSpeech(text);
      const url = URL.createObjectURL(blob);
      try {
        const audio = new Audio(url);
        await new Promise<void>((resolve) => {
          audio.onended = () => resolve();
          audio.onerror = () => resolve();
          audio.play().catch(() => resolve());
        });
      } finally {
        URL.revokeObjectURL(url);
      }
    } catch {
      // Non-fatal: the assistant's reply is already shown in the transcript.
    } finally {
      voiceStatus = null;
    }
  }

  function handleEvent(event: RunEvent) {
    if (event.type === 'message' && event.text) {
      const role = event.role ?? 'assistant';
      transcript = [...transcript, { role, text: event.text }];
      if (role === 'assistant') {
        void speak(event.text);
      }
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
    voiceStatus = 'Thinking…';
    try {
      await sendChatMessage(conversationId, text, handleEvent);
    } catch (err) {
      error = err instanceof DurableApiError ? err.message : 'Failed to send message';
    } finally {
      sending = false;
      voiceStatus = null;
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

  async function startRecording() {
    if (recording || sending) return;
    micError = null;
    try {
      activeRecorder = await startPcmRecording();
      recording = true;
      voiceStatus = 'Listening…';
    } catch (err) {
      micError = err instanceof Error ? err.message : 'Could not access the microphone';
    }
  }

  async function stopRecording() {
    if (!recording || !activeRecorder) return;
    recording = false;
    voiceStatus = 'Transcribing…';
    const recorder = activeRecorder;
    activeRecorder = null;
    try {
      const buffer = await recorder.stop();
      const text = await transcribeAudio(buffer);
      voiceStatus = null;
      if (text.trim()) {
        await sendText(text);
      }
    } catch (err) {
      error = err instanceof DurableApiError ? err.message : 'Failed to transcribe audio';
      voiceStatus = null;
    }
  }

  onDestroy(() => stopWatching?.());
</script>

<h1 class="govuk-heading-l">Voice</h1>

{#if error}
  <p class="govuk-error-message">{error}</p>
{/if}

{#if micError}
  <p class="govuk-error-message">{micError}</p>
{/if}

<RunPicker workflows={activeWorkflows} onresume={resume} />

<TranscriptView lines={transcript} />

{#if voiceStatus}
  <p class="govuk-body govuk-hint">{voiceStatus}</p>
{/if}

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

<div class="govuk-!-margin-bottom-6">
  {#if !recording}
    <button
      class="govuk-button"
      type="button"
      disabled={!!status || sending}
      onclick={startRecording}
    >
      Start speaking
    </button>
  {:else}
    <button class="govuk-button govuk-button--warning" type="button" onclick={stopRecording}>
      Stop and send
    </button>
  {/if}
</div>

<details class="govuk-details govuk-!-margin-bottom-6" data-module="govuk-details">
  <summary class="govuk-details__summary">
    <span class="govuk-details__summary-text">Type instead</span>
  </summary>
  <div class="govuk-details__text">
    <form
      onsubmit={(event) => {
        event.preventDefault();
        submitDraft();
      }}
    >
      <div class="govuk-form-group">
        <label class="govuk-label" for="voice-fallback-input">Message</label>
        <input
          class="govuk-input"
          id="voice-fallback-input"
          type="text"
          bind:value={draft}
          disabled={!!status || sending || recording}
        />
      </div>
      <button class="govuk-button" type="submit" disabled={!!status || sending || recording}>
        Send
      </button>
    </form>
  </div>
</details>

<TraceSidebar {traces} />
