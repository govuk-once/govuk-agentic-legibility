<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/state';
  import { onDestroy, untrack } from 'svelte';
  // Shared (src/lib/api/client.ts): run API calls, the journey definition and suggestions
  import {
    DurableApiError,
    getPrefillSuggestion,
    getRunState,
    getWorkflowDefinition,
    submitRunInput
  } from '$lib/api/client';
  // Shared (src/lib/api/sse.ts): live events for the run
  import { watchRun } from '$lib/api/sse';
  // Shared (src/lib/components/forms/FileRefField.svelte): file picker for upload questions
  import FileRefField from '$lib/components/forms/FileRefField.svelte';
  // Shared (src/lib/schema/kind.ts): the option type
  import type { Choice } from '$lib/schema/kind';
  // Shared (src/lib/types.ts): prompt, suggestion and event types
  import type { AwaitingInput, PrefillSuggestion, RunEvent } from '$lib/types';
  import AnswerView from '$lib/mvi/AnswerView.svelte';
  import CallEnded from '$lib/mvi/CallEnded.svelte';
  import { clockText, describeWorkflow, tidyClosingMessage, tidyText } from '$lib/mvi/format';
  import Keypad from '$lib/mvi/Keypad.svelte';
  import {
    appendChar,
    backspace,
    emptyEntry,
    pressKey,
    type EntryState,
    type KeypadMode
  } from '$lib/mvi/keypad-state';
  import PhoneShell from '$lib/mvi/PhoneShell.svelte';
  import QuestionView from '$lib/mvi/QuestionView.svelte';
  import {
    applyChoiceDigit,
    choiceDisplay,
    choiceNumber,
    choiceSubmission,
    liveChoiceKeys,
    modelFor,
    suggestedNumbers,
    suggestedText,
    textIsComplete,
    textReadout,
    textSubmission,
    type QuestionModel
  } from '$lib/mvi/question';

  const runId = page.params.workflowId!;

  interface Answer {
    question: string;
    answer: string;
  }

  let awaiting = $state<AwaitingInput | null>(null);
  let status: string | null = $state(null);
  // What the service said over the whole call, read from the run once it ends.
  let finalMessages: string[] = $state([]);
  let answers: Answer[] = $state([]);
  let submitError: string | null = $state(null);
  let submitting = $state(false);

  let department = $state('');
  let journey = $state('');

  // The call timer.
  const startedAt = Date.now();
  let elapsed = $state(0);

  // What the caller has keyed for the current question.
  let entry: EntryState = $state(emptyEntry);
  let mode: KeypadMode = $state('letters');
  let choiceEntry = $state('');
  let multiNumbers: number[] = $state([]);
  let fileValue: { ref: string; bytes: number } | null = $state(null);

  // Suggestions drawn from the context panel.
  let hasContext = $state(false);
  let suggestion: PrefillSuggestion | null = $state(null);
  let suggestionDismissed = $state(false);

  const ended = $derived(status !== null && status !== 'RUNNING' && awaiting === null);

  $effect(() => {
    if (ended) return;
    const timer = setInterval(() => {
      elapsed = Math.floor((Date.now() - startedAt) / 1000);
    }, 1000);
    return () => clearInterval(timer);
  });

  $effect(() => {
    getWorkflowDefinition(runId)
      .then((definition) => {
        const described = describeWorkflow(definition.id);
        department = described.department;
        journey = described.journey;
      })
      .catch(() => {
        // The call still works without the department and journey names.
      });
  });

  // ---- The current question ------------------------------------------------

  const baseModel = $derived(awaiting ? modelFor(awaiting) : null);

  // A text question with a worthwhile suggestion is first asked as a yes/no confirmation.
  const offered = $derived(
    baseModel && !suggestionDismissed && entry.text.length === 0 ? suggestedText(baseModel, suggestion) : null
  );

  const confirmChoices: Choice[] = [
    { value: 'use', label: 'Yes, use it' },
    { value: 'key', label: "No, I'll key it in" }
  ];

  const model: QuestionModel | null = $derived(
    offered ? { type: 'choice', multi: false, boolean: false, byIndex: false, choices: confirmChoices } : baseModel
  );

  const promptText = $derived(tidyText(awaiting?.prompt ?? ''));
  const promptLines = $derived(promptText.split('\n').filter((line) => line.trim() !== ''));
  const questionText = $derived(offered ? `Do you want to use ${offered}?` : promptText);

  const choices = $derived(model?.type === 'choice' ? model.choices : null);
  const choiceCount = $derived(choices?.length ?? 0);

  const highlighted = $derived.by(() => {
    if (model?.type !== 'choice') return [];
    if (model.multi) return multiNumbers;
    const number = choiceNumber(choiceEntry, choiceCount);
    return number ? [number] : [];
  });

  // Options the context suggests. For a suggested text answer the offer is "Yes, use it", which is
  // option 1. These show on the list and on the keypad, so the caller needn't press the key.
  const suggestedNums = $derived(offered ? [1] : baseModel ? suggestedNumbers(baseModel, suggestion) : []);

  // The question view shows until the first key is pressed, then the answer view.
  const inAnswer = $derived(
    model?.type === 'choice'
      ? choiceEntry !== '' || multiNumbers.length > 0
      : model?.type === 'text'
        ? entry.text.length > 0
        : false
  );

  const readout = $derived.by(() => {
    if (model?.type === 'choice') return highlighted.length > 0 ? highlighted.join(', ') : choiceEntry;
    if (model?.type === 'text') return textReadout(model.classification, entry.text);
    return '';
  });

  const caption = $derived.by(() => {
    if (model?.type === 'choice' && highlighted.length > 0) return choiceDisplay(model, highlighted);
    return journey;
  });

  const canConfirm = $derived.by(() => {
    if (!awaiting || !model || submitting) return false;
    if (model.type === 'choice') return highlighted.length > 0 || (!inAnswer && suggestedNums.length > 0);
    if (model.type === 'text') return textIsComplete(model.classification, entry.text);
    return false;
  });

  const canErase = $derived(inAnswer);

  const showModeToggle = $derived(model?.type === 'text' && model.classification.format === 'text');

  // Choice questions always use the number keys; only text questions can show letters.
  const keypadMode: KeypadMode = $derived(model?.type === 'text' ? mode : 'digits');

  function isLive(digit: string): boolean {
    if (!model || submitting) return false;
    if (model.type === 'choice') return liveChoiceKeys(choiceCount).has(digit);
    return model.type === 'text';
  }

  // ---- Keying --------------------------------------------------------------

  function clear() {
    entry = emptyEntry;
    choiceEntry = '';
    multiNumbers = [];
  }

  function press(digit: string) {
    if (!model || submitting) return;
    submitError = null;

    if (model.type === 'choice') {
      if (!liveChoiceKeys(choiceCount).has(digit)) return;
      if (model.multi) {
        const number = Number(digit);
        multiNumbers = multiNumbers.includes(number)
          ? multiNumbers.filter((existing) => existing !== number)
          : [...multiNumbers, number].sort((a, b) => a - b);
      } else {
        choiceEntry = applyChoiceDigit(choiceEntry, digit, choiceCount);
      }
    } else if (model.type === 'text') {
      entry = pressKey(entry, digit, mode, Date.now(), model.classification.maxLength);
    }
  }

  function erase() {
    if (!model) return;
    if (model.type === 'choice') {
      if (model.multi) multiNumbers = multiNumbers.slice(0, -1);
      else choiceEntry = choiceEntry.slice(0, -1);
    } else if (model.type === 'text') {
      entry = backspace(entry);
    }
  }

  function toggleMode() {
    mode = mode === 'digits' ? 'letters' : 'digits';
    entry = { ...entry, pending: null };
  }

  // ---- Submitting ----------------------------------------------------------

  async function send(value: unknown, display: string) {
    if (!awaiting) return;
    submitError = null;
    submitting = true;
    try {
      await submitRunInput(runId, awaiting.token, value);
      answers = [...answers, { question: promptLines[0] ?? awaiting.prompt, answer: display }];
      awaiting = null;
      clear();
    } catch (error) {
      submitError = error instanceof DurableApiError ? error.message : 'Failed to send your answer';
    } finally {
      submitting = false;
    }
  }

  async function confirm() {
    if (!canConfirm || !awaiting || !model) return;

    if (model.type === 'choice') {
      const numbers = highlighted.length > 0 ? highlighted : suggestedNums;
      if (offered) {
        if (numbers[0] === 1) {
          await send(offered, offered);
        } else {
          suggestionDismissed = true;
          clear();
        }
        return;
      }
      await send(choiceSubmission(model, numbers), choiceDisplay(model, numbers));
    } else if (model.type === 'text') {
      const value = textSubmission(model.classification, entry.text);
      await send(value, value);
    }
  }

  async function sendFile() {
    if (fileValue) await send(fileValue, fileValue.ref);
  }

  // The physical keyboard does the same as the on-screen keypad.
  function onKeydown(event: KeyboardEvent) {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    const target = event.target as HTMLElement | null;
    if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
    if (!awaiting || !model || model.type === 'file' || submitting) return;

    if (/^[0-9]$/.test(event.key)) {
      event.preventDefault();
      press(event.key);
    } else if (event.key === 'Backspace') {
      event.preventDefault();
      erase();
    } else if (event.key === 'Enter') {
      if (target && ['BUTTON', 'A'].includes(target.tagName)) return;
      event.preventDefault();
      void confirm();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      clear();
    } else if (
      model.type === 'text' &&
      mode === 'letters' &&
      /^[a-zA-Z .,'@-]$/.test(event.key)
    ) {
      event.preventDefault();
      entry = appendChar(entry, event.key, model.classification.maxLength);
    }
  }

  // ---- The run -------------------------------------------------------------

  async function refreshAwaiting() {
    try {
      const state = await getRunState(runId);
      awaiting = state.awaiting;
      status = state.status;
    } catch (error) {
      submitError = error instanceof DurableApiError ? error.message : 'Failed to load the call';
    }
  }

  function handleEvent(event: RunEvent) {
    if (event.type === 'options') {
      // The event doesn't carry the token the answer needs, so fetch the run state.
      void refreshAwaiting();
    } else if (event.type === 'completed') {
      status = event.status ?? 'COMPLETED';
      awaiting = null;
      stopWatching();
      void loadFinalMessages();
    }
  }

  // The run's transcript holds what the service said, without the questions it asked.
  async function loadFinalMessages() {
    try {
      const state = await getRunState(runId);
      finalMessages = state.transcript
        .map((entry) => tidyText(entry.message ?? ''))
        .filter((message) => message !== '' && !message.startsWith('[ENGINE LOG]'))
        .map(tidyClosingMessage)
        .filter((message) => message !== '');
    } catch {
      // The ended screen still shows without the messages.
    }
  }

  const stopWatching = browser ? watchRun(runId, handleEvent) : () => {};
  onDestroy(stopWatching);

  // ---- Suggestions ---------------------------------------------------------

  async function fetchSuggestion() {
    if (!awaiting || !hasContext) {
      suggestion = null;
      return;
    }
    const token = awaiting.token;
    try {
      const result = await getPrefillSuggestion(runId, awaiting);
      if (awaiting?.token === token) suggestion = result;
    } catch {
      suggestion = null;
    }
  }

  // The facts were typed on the start screen and saved against this call. Shared: they are read
  // back from the same /api/web/.../context route the /web page uses.
  $effect(() => {
    fetch(`/api/web/${encodeURIComponent(runId)}/context`)
      .then((response) => (response.ok ? response.json() : null))
      .then((body: { context?: string | null } | null) => {
        if (body?.context) {
          hasContext = true;
          void fetchSuggestion();
        }
      })
      .catch(() => {
        // Without the facts the call simply has no suggestions.
      });
  });

  // Each new question starts clean.
  let lastToken: string | null = null;
  $effect(() => {
    const token = awaiting?.token ?? null;
    if (token === lastToken) return;
    lastToken = token;
    untrack(() => {
      clear();
      suggestion = null;
      suggestionDismissed = false;
      fileValue = null;
      if (awaiting) {
        const next = modelFor(awaiting);
        if (next.type === 'text') mode = next.classification.startMode;
        void fetchSuggestion();
      }
    });
  });
</script>

<svelte:window onkeydown={onKeydown} />

<PhoneShell
  {department}
  clock={clockText(elapsed)}
  showKeypad={!ended && awaiting !== null && model !== null && model.type !== 'file'}
  top={ended}
  scrollKey={`${awaiting?.token ?? (ended ? 'ended' : 'waiting')}-${inAnswer}`}
>
      {#if ended}
        <CallEnded status={status ?? 'COMPLETED'} clock={clockText(elapsed)} messages={finalMessages} {answers} />
      {:else if awaiting && model}
        {#if model.type === 'file'}
          <QuestionView
            prompt={questionText}
            choices={null}
            highlighted={[]}
            suggested={[]}
            error={submitError}
          />
          <FileRefField schema={awaiting.schema} bind:value={fileValue} />
          <button
            type="button"
            class="govuk-button govuk-!-margin-top-4"
            disabled={!fileValue || submitting}
            onclick={sendFile}
          >
            Continue
          </button>
        {:else if inAnswer}
          <AnswerView {readout} {caption} error={submitError} />
        {:else}
          <QuestionView
            prompt={questionText}
            {choices}
            {highlighted}
            suggested={suggestedNums}
            error={submitError}
          />
        {/if}
      {:else}
        <p class="govuk-body ss-muted">Connecting…</p>
      {/if}

      {#snippet keypad()}
        {#if !ended && awaiting && model && model.type !== 'file'}
          <Keypad
            mode={keypadMode}
            live={isLive}
            chosen={model.type === 'choice' ? (highlighted.length > 0 ? highlighted : suggestedNums).map(String) : []}
            {canConfirm}
            {canErase}
            {showModeToggle}
            onkey={press}
            onerase={erase}
            onconfirm={confirm}
            ontoggle={toggleMode}
          />
        {/if}
      {/snippet}
</PhoneShell>
