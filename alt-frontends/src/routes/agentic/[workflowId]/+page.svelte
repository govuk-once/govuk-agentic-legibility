<script lang="ts">
  import { browser } from '$app/environment';
  import { replaceState } from '$app/navigation';
  import { page } from '$app/state';
  import { onDestroy } from 'svelte';
  import {
    DurableApiError,
    getAutonomy,
    getRunState,
    resumeAutonomy,
    setAutonomy,
    submitRunInput
  } from '$lib/api/client';
  import { watchRun } from '$lib/api/sse';
  import KindField from '$lib/components/forms/KindField.svelte';
  import AgentActivityList from '$lib/components/agentic/AgentActivityList.svelte';
  import AgentNeedsYouCard from '$lib/components/agentic/AgentNeedsYouCard.svelte';
  import AgentRunHeader from '$lib/components/agentic/AgentRunHeader.svelte';
  import AgentRunProgress from '$lib/components/agentic/AgentRunProgress.svelte';
  import AgentRunStepList from '$lib/components/agentic/AgentRunStepList.svelte';
  import AgentTabs from '$lib/components/agentic/AgentTabs.svelte';
  // Shared (src/lib/mvi/format.ts): turns a journey id such as "dvla.change_of_address" into a readable name
  import { describeWorkflow } from '$lib/mvi/format';
  // Shared (src/lib/mvi02/answers.ts): turns a submitted answer into readable text, for example an option number into its label
  import { displayValue } from '$lib/mvi02/answers';
  import type { AutonomyPolicy, AwaitingInput, RunEvent, SchemaDefinition } from '$lib/types';

  const workflowId = page.params.workflowId!;

  interface LogLine {
    category?: string;
    summary?: string;
  }

  let status: string | null = $state(null);

  interface Escalation {
    token: string;
    prompt: string;
    schema: unknown;
    reason?: string;
  }

  function toAwaiting(candidate: Escalation | null): AwaitingInput | null {
    if (!candidate) return null;
    return {
      token: candidate.token,
      prompt: candidate.prompt || 'Provide a value',
      schema: (candidate.schema as AwaitingInput['schema']) ?? { kind: 'string' }
    };
  }

  let log: LogLine[] = $state([]);
  let escalation: Escalation | null = $state(null);
  let escalationAwaiting: AwaitingInput | null = $derived(toAwaiting(escalation));

  let profileFixture = $state(page.url.searchParams.get('profile') ?? '');
  let preseed = $state('');
  let autonomyLevel: AutonomyPolicy['autonomy_level'] = $state('balanced');
  let notifyCategories: string[] = $state(['identity', 'payment', 'irreversible']);
  let pauseBeforeExternalCall = $state(true);
  let continueAfterAnswer = $state(true);
  let hasSeed = $derived(!!profileFixture || !!preseed.trim());
  let policyError: string | null = $state(null);

  let resuming = $state(false);
  let resumeError: string | null = $state(null);
  let resumeAbort: AbortController | null = null;

  // A run id looks like "sfsm-dvla.change_of_address-8537ccb0": the journey id with a prefix and a
  // short random ending. It is turned into "DVLA: Change of address" for the header.
  const journeyName = (() => {
    const journeyId = workflowId.replace(/^sfsm-/, '').replace(/-[0-9a-f]{8}$/, '');
    if (!journeyId.includes('.')) return workflowId;
    const { department, journey } = describeWorkflow(journeyId);
    return `${department}: ${journey}`;
  })();

  // Which tab of the run view is showing: the trace, or the event log.
  let selectedTab = $state('trace');

  // The text of each question the run has asked, by its token. It is filled in as the questions
  // arrive on the live feed, and from the questions the agent hands to you.
  let questions: Record<string, { prompt: string; schema: unknown }> = $state({});

  // The questions answered on this page, in order, and who answered each: the agent from your facts,
  // or you. This starts empty when the page is reloaded, because the run doesn't send that history back.
  let answers: { token: string; source: 'agent' | 'you'; value: unknown }[] = $state([]);
  let stepsDone = $derived(answers.length);

  // The first line of a question is the question itself; the rest is explanation.
  function questionText(token: string): string {
    const prompt = questions[token]?.prompt ?? 'a question';
    return prompt.split('\n').find((line) => line.trim() !== '')?.trim() ?? prompt;
  }

  // One row for each answered question, then a row for the question waiting for you, if there is one.
  const stepRows = $derived.by(() => {
    const rows: { key: string; state: 'done' | 'waiting'; title: string; detail: string }[] = answers.map(
      (answer) => {
        const text = displayValue(questions[answer.token]?.schema as SchemaDefinition | undefined, answer.value);
        return {
          key: answer.token,
          state: 'done',
          title: `Asked: ${questionText(answer.token)}`,
          detail: answer.source === 'agent' ? `The agent answered ${text} from your facts` : `You answered ${text}`
        };
      }
    );
    if (escalation) {
      rows.push({
        key: escalation.token,
        state: 'waiting',
        title: `Waiting for you: ${questionText(escalation.token)}`,
        detail: escalation.reason ?? 'The agent needs your answer.'
      });
    }
    return rows;
  });

  let answeredByAgent = $derived(answers.filter((answer) => answer.source === 'agent').length);
  let answeredByYou = $derived(answers.length - answeredByAgent);
  let finished = $derived(!!status && status !== 'RUNNING');

  // The agent can be started again when nothing is running, nothing is waiting for you and the run
  // has not finished.
  let canResume = $derived(!resuming && !escalation && !finished);

  // One sentence on where the run stands.
  let progressSummary = $derived.by(() => {
    if (finished) return `The run is complete. The agent answered ${answeredByAgent} on its own and you answered ${answeredByYou}.`;
    if (escalation) return `The agent has answered ${answeredByAgent} on its own. It has stopped because it needs your answer.`;
    if (resuming) return 'The agent is working through the journey.';
    return 'The agent is paused. Resume it to carry on.';
  });

  // What the run is doing, in words and as a tag colour.
  const runStatus = $derived.by((): { label: string; colour: 'blue' | 'green' | 'grey' | 'yellow' } => {
    if (escalation) return { label: 'Waiting for you', colour: 'yellow' };
    if (status && status !== 'RUNNING') return { label: 'Complete', colour: 'green' };
    if (resuming) return { label: 'Agent working', colour: 'blue' };
    return { label: 'Paused', colour: 'grey' };
  });

  let headerSummary = $derived([
    journeyName,
    `${autonomyLevel.charAt(0).toUpperCase()}${autonomyLevel.slice(1)}`,
    `${stepsDone === 1 ? '1 step' : `${stepsDone} steps`} done`
  ]);

  $effect(() => {
    getRunState(workflowId)
      .then((state) => {
        status = state.status;
      })
      .catch(() => {
        // Non-fatal: the status just stays blank until the live feed reports it.
      });

    getAutonomy(workflowId)
      .then((config) => {
        if (config) {
          profileFixture = config.profile_fixture;
          preseed = config.preseed ?? '';
          autonomyLevel = config.policy.autonomy_level;
          notifyCategories = [...config.policy.notify_categories];
          pauseBeforeExternalCall = config.policy.pause_before_external_call;
        }
        // The start page asks for this; drop it from the URL so a reload doesn't re-run.
        if (page.url.searchParams.has('autorun')) {
          const url = new URL(page.url);
          url.searchParams.delete('autorun');
          replaceState(url, {});
          if (config) void resume();
        }
      })
      .catch(() => {
        // Non-fatal: the panel keeps its defaults, and saving writes a fresh config.
      });
  });

  function describeValue(value: unknown): string {
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    return text.length > 60 ? `${text.slice(0, 57)}…` : text;
  }

  function handleEvent(event: RunEvent) {
    if (event.type === 'trace') {
      log = [...log, { category: event.category, summary: event.summary }];
      // The live feed reports each question as "Awaiting InputState [token]" with its text.
      const token = /^Awaiting InputState \[(.+)\]$/.exec(event.summary ?? '')?.[1];
      const detail = event.detail as { prompt?: string; schema?: unknown } | undefined;
      if (token && detail?.prompt) questions[token] = { prompt: detail.prompt, schema: detail.schema };
    } else if (event.type === 'completed') {
      status = event.status ?? 'COMPLETED';
    }
  }

  // EventSource only exists in the browser; SSR renders without the live feed.
  const stopWatching = browser ? watchRun(workflowId, handleEvent) : () => {};
  onDestroy(() => {
    stopWatching();
    resumeAbort?.abort();
  });

  async function savePolicy(): Promise<boolean> {
    if (!hasSeed) return false;
    policyError = null;
    try {
      await setAutonomy(workflowId, {
        policy: {
          autonomy_level: autonomyLevel,
          notify_categories: notifyCategories,
          pause_before_external_call: pauseBeforeExternalCall
        },
        profile_fixture: profileFixture,
        preseed
      });
      return true;
    } catch (error) {
      policyError = error instanceof DurableApiError ? error.message : 'Failed to save policy';
      return false;
    }
  }

  async function resume() {
    resumeError = null;
    escalation = null;
    // Save first so edits to the facts or policy apply without a separate click.
    if (!(await savePolicy())) return;
    resuming = true;
    resumeAbort = new AbortController();
    try {
      await resumeAutonomy(
        workflowId,
        (event) => {
          if (event.type === 'trace') {
            const detail = event.detail as { token?: string; value?: unknown } | undefined;
            const summary =
              detail && 'value' in detail ? `${event.summary}: ${describeValue(detail.value)}` : event.summary;
            log = [...log, { category: event.category, summary }];
            if (event.summary?.startsWith('Autonomously resolved field') && detail?.token) {
              answers = [...answers, { token: detail.token, source: 'agent', value: detail.value }];
            }
          } else if (event.type === 'escalation') {
            log = [...log, { category: event.category ?? 'AGENT', summary: event.summary }];
            if (event.detail?.token) {
              questions[event.detail.token] = { prompt: event.detail.prompt ?? '', schema: event.detail.schema };
            }
            escalation = {
              token: event.detail?.token ?? '',
              prompt: event.detail?.prompt ?? 'Provide a value',
              schema: event.detail?.schema,
              reason: event.detail?.reason
            };
          } else if (event.type === 'completed') {
            status = event.status ?? 'COMPLETED';
          }
        },
        resumeAbort.signal
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        resumeError = error instanceof DurableApiError ? error.message : 'Autonomous resume failed';
      }
    } finally {
      resuming = false;
      resumeAbort = null;
      void refreshCurrentState();
    }
  }

  function stopResume() {
    resumeAbort?.abort();
  }

  async function refreshCurrentState() {
    try {
      const state = await getRunState(workflowId);
      status = state.status;
    } catch {
      // Best-effort refresh; the SSE feed will catch up if this fails.
    }
  }

  async function handleEscalationSubmit(value: unknown) {
    if (!escalation) return;
    try {
      await submitRunInput(workflowId, escalation.token, value);
      answers = [...answers, { token: escalation.token, source: 'you', value }];
      escalation = null;
      await refreshCurrentState();
      if (continueAfterAnswer && status !== 'COMPLETED') void resume();
    } catch (error) {
      resumeError = error instanceof DurableApiError ? error.message : 'Failed to submit input';
    }
  }
</script>

<div class="agent-run-page">
<AgentRunHeader
  runId={workflowId}
  statusLabel={runStatus.label}
  statusColour={runStatus.colour}
  summary={headerSummary}
  canStop={resuming}
  onstop={stopResume}
/>

<AgentTabs
  tabs={[
    { id: 'trace', label: 'Trace' },
    { id: 'events', label: 'Event log' }
  ]}
  bind:selected={selectedTab}
>
  {#snippet children(tabId)}
    {#if tabId === 'trace'}
<div class="agentic-dashboard">
  <div class="agentic-dashboard__steps">
    <AgentRunStepList steps={stepRows} />
  </div>

  <div class="agentic-dashboard__panel">
    {#if escalationAwaiting}
      <AgentNeedsYouCard step={stepsDone + 1} reason={escalation?.reason} bind:continueAfterAnswer>
        <KindField awaiting={escalationAwaiting} onsubmit={handleEscalationSubmit} />
      </AgentNeedsYouCard>
    {/if}

    <AgentRunProgress
      summary={progressSummary}
      done={stepsDone}
      {answeredByYou}
      needsYou={!!escalation}
      onresume={canResume ? resume : undefined}
      error={resumeError ?? policyError}
    />

    <div class="govuk-!-margin-top-6">
      <AgentActivityList events={log} />
    </div>
  </div>
</div>
    {:else}
      <p class="govuk-body ss-muted agent-run-page__empty">The event log is built in a later step.</p>
    {/if}
  {/snippet}
</AgentTabs>
</div>

<style>
  /* The page is wider than the 960px GOV.UK container it sits in, centred on the same line, and
     shrinks to fit narrow windows. The design is laid out for a wide screen. */
  .agent-run-page {
    width: min(1360px, 100vw - 80px);
    margin-left: calc(50% - min(680px, 50vw - 40px));
  }

  /* Text boxes and buttons have softly rounded corners, and buttons have no line under them, as on
     the other redesigned pages. */
  .agent-run-page :global(.govuk-input),
  .agent-run-page :global(.govuk-select),
  .agent-run-page :global(.govuk-textarea) {
    border-radius: 8px;
  }

  .agent-run-page :global(.govuk-button) {
    border-radius: 8px;
    box-shadow: none;
  }

  /* gov.css gives a focused button a black line under it. That is removed too; the yellow fill
     stays as the sign of focus. */
  .agent-run-page :global(.govuk-button:focus:not(:active):not(:hover)) {
    box-shadow: none;
  }

  .agent-run-page__empty {
    padding: 20px;
    margin: 0;
  }

  /* The Trace tab has the list of steps on the left and the controls and activity on the right, with
     a line between them. */
  .agentic-dashboard {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
    align-items: stretch;
  }

  .agentic-dashboard__panel {
    padding: 20px;
    border-left: 1px solid #b1b4b6;
  }
</style>
