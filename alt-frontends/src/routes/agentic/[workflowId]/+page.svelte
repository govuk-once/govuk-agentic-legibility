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
  import AgentEventLog from '$lib/components/agentic/AgentEventLog.svelte';
  import AgentNeedsYouCard from '$lib/components/agentic/AgentNeedsYouCard.svelte';
  import AgentRunHeader from '$lib/components/agentic/AgentRunHeader.svelte';
  import AgentRunMetrics from '$lib/components/agentic/AgentRunMetrics.svelte';
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
    /** The raw detail the event came with, shown in the Event log's technical column. */
    detail?: unknown;
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
  // Each answer also records when its step started and ended, in milliseconds, as measured on this page.
  let answers: { token: string; source: 'agent' | 'you'; value: unknown; startedAt: number; endedAt: number }[] =
    $state([]);

  // Timing, measured on this page as events arrive. The run doesn't send times for questions and
  // answers, so these are the page's own clock: when the first step began, when the step now under
  // way began, and when the question waiting for you appeared.
  let timelineStart: number | null = $state(null);
  let stepStartedAt: number | null = null;
  let waitingSince: number | null = $state(null);

  // The clock for the question that is waiting, so its time counts up while you read it.
  let now = $state(Date.now());
  $effect(() => {
    if (waitingSince === null) return;
    const timer = setInterval(() => (now = Date.now()), 250);
    return () => clearInterval(timer);
  });

  // "2.7s", or "1m 12s" for a long wait.
  function formatDuration(milliseconds: number): string {
    const seconds = milliseconds / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  }
  let stepsDone = $derived(answers.length);

  // The first line of a question is the question itself; the rest is explanation.
  function questionText(token: string): string {
    const prompt = questions[token]?.prompt ?? 'a question';
    return prompt.split('\n').find((line) => line.trim() !== '')?.trim() ?? prompt;
  }

  // When the run's timeline ends: when the latest step ended, or now if a question is waiting for you.
  const timelineEnd = $derived(
    Math.max(0, ...answers.map((answer) => answer.endedAt), waitingSince === null ? 0 : now)
  );

  // How the run's measured time splits between the agent working and you answering.
  const timeSplit = $derived.by(() => {
    const agentMs = answers
      .filter((answer) => answer.source === 'agent')
      .reduce((sum, answer) => sum + (answer.endedAt - answer.startedAt), 0);
    const yourMs =
      answers.filter((answer) => answer.source === 'you').reduce((sum, answer) => sum + (answer.endedAt - answer.startedAt), 0) +
      (waitingSince === null ? 0 : now - waitingSince);
    return { agentMs, yourMs };
  });

  // How many times the agent decided something: each question it answered from your facts, and each
  // time it stopped to ask you. Each of these took at least one call to the model, so this is a lower
  // bound on the number of model calls, which the run doesn't report.
  const agentDecisions = $derived(
    answers.filter((answer) => answer.source === 'agent').length +
      log.filter((line) => line.summary?.startsWith('Escalated to human') || line.summary?.startsWith('No progress made')).length
  );

  // The figures for the top of the Event log.
  const runFigures = $derived([
    { label: 'Events logged', value: String(log.length) },
    { label: 'Agent decisions', value: String(agentDecisions) },
    { label: 'Answered by agent', value: `${answers.filter((answer) => answer.source === 'agent').length} of ${answers.length}` },
    { label: 'Waiting on you', value: formatDuration(timeSplit.yourMs) },
    { label: 'Run time', value: timelineStart === null ? '—' : formatDuration(timelineEnd - timelineStart) }
  ]);

  // The bar under them splits the events in the log by who produced them: the engine (and the system),
  // the agent, and you. Each part is shown as a percentage of all the events. It stays empty until
  // there is an event.
  const runSplit = $derived.by((): { label: string; share: number; colour: 'engine' | 'agent' | 'you' }[] => {
    const counts = { engine: 0, agent: 0, you: 0 };
    for (const line of log) {
      const category = line.category?.toLowerCase();
      if (category === 'agent') counts.agent += 1;
      else if (category === 'user') counts.you += 1;
      else counts.engine += 1;
    }
    const total = log.length;
    if (total === 0) return [];
    // The last share takes whatever is left, so the three always add up to 100.
    const engineShare = Math.round((counts.engine / total) * 100);
    const agentShare = Math.min(Math.round((counts.agent / total) * 100), 100 - engineShare);
    return [
      { label: 'Engine', share: engineShare, colour: 'engine' },
      { label: 'Agent', share: agentShare, colour: 'agent' },
      { label: 'You', share: 100 - engineShare - agentShare, colour: 'you' }
    ];
  });

  // Whether the Event log shows the raw detail of each event.
  let showTechnical = $state(false);

  // One row for each answered question, then a row for the question waiting for you, if there is one.
  // Each row has its time and a bar: how far along the run the step began, and how much of the run
  // it took. A bar is never thinner than 1.5% so a very quick step can still be seen.
  const stepRows = $derived.by(() => {
    const start = timelineStart;
    const total = start === null ? 0 : Math.max(timelineEnd - start, 1);

    function timing(from: number, to: number) {
      if (start === null) return {};
      return {
        time: formatDuration(to - from),
        bar: {
          left: Math.min(((from - start) / total) * 100, 98.5),
          width: Math.max(((to - from) / total) * 100, 1.5)
        }
      };
    }

    const rows: {
      key: string;
      state: 'done' | 'waiting';
      title: string;
      detail: string;
      time?: string;
      bar?: { left: number; width: number };
    }[] = answers.map((answer) => {
      const text = displayValue(questions[answer.token]?.schema as SchemaDefinition | undefined, answer.value);
      return {
        key: answer.token,
        state: 'done',
        title: `Asked: ${questionText(answer.token)}`,
        detail: answer.source === 'agent' ? `The agent answered ${text} from your facts` : `You answered ${text}`,
        ...timing(answer.startedAt, answer.endedAt)
      };
    });
    if (escalation) {
      rows.push({
        key: escalation.token,
        state: 'waiting',
        title: `Waiting for you: ${questionText(escalation.token)}`,
        detail: escalation.reason ?? 'The agent needs your answer.',
        ...(waitingSince === null ? {} : timing(waitingSince, now))
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
      log = [...log, { category: event.category, summary: event.summary, detail: event.detail }];
      // The live feed reports each question as "Awaiting InputState [token]" with its text.
      const token = /^Awaiting InputState \[(.+)\]$/.exec(event.summary ?? '')?.[1];
      const detail = event.detail as { prompt?: string; schema?: unknown } | undefined;
      if (token && detail?.prompt) questions[token] = { prompt: detail.prompt, schema: detail.schema };
    } else if (event.type === 'completed') {
      status = event.status ?? 'COMPLETED';
      // The server closes the feed when the run ends. A browser reconnects to a closed feed by itself,
      // and each reconnect replays the whole run, so the feed is closed here to stop that.
      stopWatching();
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
    stepStartedAt = Date.now();
    timelineStart ??= stepStartedAt;
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
            log = [...log, { category: event.category, summary, detail: event.detail }];
            if (event.summary?.startsWith('Autonomously resolved field') && detail?.token) {
              const endedAt = Date.now();
              answers = [
                ...answers,
                { token: detail.token, source: 'agent', value: detail.value, startedAt: stepStartedAt ?? endedAt, endedAt }
              ];
              stepStartedAt = endedAt;
            }
          } else if (event.type === 'escalation') {
            log = [...log, { category: event.category ?? 'AGENT', summary: event.summary, detail: event.detail }];
            if (event.detail?.token) {
              questions[event.detail.token] = { prompt: event.detail.prompt ?? '', schema: event.detail.schema };
            }
            waitingSince = Date.now();
            now = waitingSince;
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
      const endedAt = Date.now();
      answers = [
        ...answers,
        { token: escalation.token, source: 'you', value, startedAt: waitingSince ?? endedAt, endedAt }
      ];
      // Your answer is an event in the log too, labelled "You".
      const answerText = displayValue(escalation.schema as SchemaDefinition | undefined, value);
      log = [
        ...log,
        { category: 'USER', summary: `You answered "${questionText(escalation.token)}": ${answerText}`, detail: { token: escalation.token, value } }
      ];
      waitingSince = null;
      stepStartedAt = endedAt;
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
      <AgentRunMetrics figures={runFigures} split={runSplit} />
      <AgentEventLog events={log} {showTechnical} />
    {/if}
  {/snippet}

  {#snippet aside()}
    {#if selectedTab === 'events'}
      <div class="govuk-checkboxes govuk-checkboxes--small agent-run-page__technical">
        <div class="govuk-checkboxes__item">
          <input class="govuk-checkboxes__input" id="show-technical" type="checkbox" bind:checked={showTechnical} />
          <label class="govuk-label govuk-checkboxes__label" for="show-technical">Show technical detail</label>
        </div>
      </div>
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

  /* The "Show technical detail" switch in the tab bar stays on one line. */
  .agent-run-page__technical :global(.govuk-checkboxes__label) {
    max-width: none;
    white-space: nowrap;
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
