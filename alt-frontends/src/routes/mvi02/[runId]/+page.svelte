<script lang="ts">
  import { page } from '$app/state';
  import { untrack } from 'svelte';
  // Shared (src/lib/api/client.ts): asks the facts for a suggestion when the agent is off
  import { getPrefillSuggestion } from '$lib/api/client';
  // Shared (src/lib/components/forms/FileRefField.svelte): file picker for upload questions
  import FileRefField from '$lib/components/forms/FileRefField.svelte';
  // Shared (src/lib/mvi/format.ts): the call timer text
  import { clockText } from '$lib/mvi/format';
  import { displayValue, questionLabel } from '$lib/mvi02/answers';
  import { CallController } from '$lib/mvi02/call-controller.svelte';
  import Icon from '$lib/mvi02/Icon.svelte';
  import Keypad from '$lib/mvi02/Keypad.svelte';
  import { KeypadSession } from '$lib/mvi02/keypad-session.svelte';
  import Phone from '$lib/mvi02/Phone.svelte';
  import ReviewList from '$lib/mvi02/ReviewList.svelte';
  import QuestionCard from '$lib/mvi02/QuestionCard.svelte';
  import Review from '$lib/mvi02/Review.svelte';

  const runId = page.params.runId!;
  const agent = page.url.searchParams.get('agent') === '1';
  const autorun = page.url.searchParams.get('auto') === '1';

  const controller = new CallController(runId, agent, autorun);
  const session = new KeypadSession(() => controller.awaiting);

  let fileValue: { ref: string; bytes: number } | null = $state(null);
  let hasContext = $state(false);

  $effect(() => {
    controller.start();
    return () => controller.destroy();
  });

  // ---- The card ------------------------------------------------------------------------------

  const asking = agent ? 'Agent is asking' : 'The service is asking';
  const ended = $derived(controller.phase === 'ended');

  // The keypad only works while a question is waiting for the caller.
  const keypadActive = $derived(
    controller.phase === 'asking' && session.model !== null && session.model.type !== 'file' && !controller.submitting
  );

  const cardView = $derived.by(() => {
    if (controller.phase === 'paused') return 'paused' as const;
    if (controller.phase === 'asking' && session.model) return session.view;
    return 'working' as const;
  });

  const agentAnswered = $derived(controller.answers.filter((answer) => answer.source === 'facts').length);

  const pill = $derived({
    label: ended ? 'Call ended' : controller.department || 'On the call',
    time: clockText(controller.elapsed),
    state: ended ? ('off' as const) : ('live' as const)
  });

  const reviewItems = $derived(
    controller.answers.map((answer) => {
      const info = controller.prompts[answer.token];
      return {
        label: info ? questionLabel(info.prompt) : 'Question',
        value: answer.display ?? displayValue(info?.schema, answer.value),
        source: answer.source
      };
    })
  );

  // ---- Answering -----------------------------------------------------------------------------

  async function confirm() {
    if (!keypadActive) return;
    const answer = session.takeAnswer();
    if (!answer) return;
    await controller.submit(answer.value, answer.display, answer.confirmed ? 'confirmed' : 'said');
  }

  async function sendFile() {
    if (fileValue) await controller.submit(fileValue, fileValue.ref, 'said');
  }

  // The physical keyboard does the same as the on-screen keypad.
  function onKeydown(event: KeyboardEvent) {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    const target = event.target as HTMLElement | null;
    if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
    if (!keypadActive) return;

    if (/^[0-9]$/.test(event.key)) {
      event.preventDefault();
      // In letter mode the on-screen keys cycle through letters, but a digit typed on a real
      // keyboard should simply be that digit.
      if (session.model?.type === 'text' && session.keypadMode === 'letters') session.typeLetter(event.key);
      else session.press(event.key);
    } else if (event.key === 'Backspace') {
      event.preventDefault();
      session.erase();
    } else if (event.key === 'Enter') {
      if (target && ['BUTTON', 'A'].includes(target.tagName)) return;
      event.preventDefault();
      void confirm();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      session.clear();
    } else if (/^[a-zA-Z .,'@-]$/.test(event.key)) {
      event.preventDefault();
      session.typeLetter(event.key);
    }
  }

  // ---- Suggestions (only when the agent is off) -----------------------------------------------

  // The facts were saved against this call on the start screen. They are read back from the same
  // route the /web page uses.
  $effect(() => {
    if (agent) return;
    fetch(`/api/web/${encodeURIComponent(runId)}/context`)
      .then((response) => (response.ok ? response.json() : null))
      .then((body: { context?: string | null } | null) => {
        if (body?.context) hasContext = true;
      })
      .catch(() => {
        // Without the facts the call simply has no suggestions.
      });
  });

  async function fetchSuggestion() {
    const awaiting = controller.awaiting;
    if (agent || !awaiting || !hasContext) return;
    const token = awaiting.token;
    try {
      const result = await getPrefillSuggestion(runId, awaiting);
      if (controller.awaiting?.token === token) session.suggestion = result;
    } catch {
      session.suggestion = null;
    }
  }

  // Each new question starts clean.
  let lastToken: string | null = null;
  $effect(() => {
    const token = controller.awaiting?.token ?? null;
    if (token === lastToken) return;
    lastToken = token;
    untrack(() => {
      session.reset();
      fileValue = null;
      void fetchSuggestion();
    });
  });

  $effect(() => {
    if (hasContext) untrack(() => void fetchSuggestion());
  });
</script>

<svelte:window onkeydown={onKeydown} />

<Phone {pill} {footer}>
  {#if ended}
    <Review items={reviewItems} closing={controller.closingMessages} />
  {:else}
    <QuestionCard
      view={cardView}
      {asking}
      prompt={session.questionText}
      choices={session.choices}
      highlighted={session.highlighted}
      suggested={session.suggestedNums}
      readout={session.readout}
      heard={session.heard}
      hint={session.hint}
      notice={session.notice}
      problem={session.problem}
      error={controller.error}
      answered={agentAnswered}
      startLabel={controller.error ? 'Try again' : 'Start answering'}
      onstart={() => controller.resume()}
    >
      {#if cardView === 'file' && controller.awaiting}
        <FileRefField schema={controller.awaiting.schema} bind:value={fileValue} />
        <button
          type="button"
          class="mvi2-btn mvi2-btn--card"
          disabled={!fileValue || controller.submitting}
          onclick={sendFile}
        >
          Continue
        </button>
      {/if}
    </QuestionCard>
  {/if}
</Phone>

{#snippet footer()}
  {#if ended}
    <div class="mvi2-actions">
      <!-- The call has already been recorded, so this only shows how the design ends. -->
      <button type="button" class="mvi2-btn">
        Submit application
        <Icon name="tick" width={20} height={16} />
      </button>
    </div>
  {:else if agent && cardView === 'working'}
    <!-- While the agent works the keypad isn't needed, so what it has answered shows in its place. -->
    <div class="mvi2-agentlog">
      {#if reviewItems.length > 0}
        <ReviewList items={reviewItems} follow />
      {:else}
        <p class="mvi2-agentlog__empty">Its answers will appear here.</p>
      {/if}
    </div>
  {:else}
    <Keypad
      mode={session.keypadMode}
      live={(digit) => keypadActive && session.isLive(digit)}
      chosen={keypadActive ? session.chosenKeys : []}
      canConfirm={keypadActive && session.canConfirm}
      canErase={keypadActive && session.canErase}
      showModeToggle={keypadActive && session.showModeToggle}
      dim={!keypadActive}
      onkey={(digit) => session.press(digit)}
      onerase={() => session.erase()}
      onconfirm={confirm}
      ontoggle={() => session.toggleMode()}
    />
  {/if}
{/snippet}
