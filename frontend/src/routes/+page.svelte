<script lang="ts">
  import {
    getApiBaseUrl,
    getJourneyTrace,
    requestJourneyAssistance,
    startJourney,
    submitJourneyResult
  } from '$lib/api';
  import AssistancePanel from '$lib/components/AssistancePanel.svelte';
  import DataSummary from '$lib/components/DataSummary.svelte';
  import DeveloperPanel from '$lib/components/DeveloperPanel.svelte';
  import SchemaForm from '$lib/components/SchemaForm.svelte';
  import type {
    AssistanceResponse,
    ConversationMessage,
    JourneyHistoryItem,
    JourneyRunResponse,
    TraceEvent
  } from '$lib/types';

  const JOURNEY_ID = 'change-driving-licence-address';
  const API_BASE_URL = getApiBaseUrl();
  let run: JourneyRunResponse | null = null;
  let traceEvents: TraceEvent[] = [];
  let history: JourneyHistoryItem[] = [];
  let conversation: ConversationMessage[] = [];
  let assistanceMessage = '';
  let assistance: AssistanceResponse | null = null;
  let proposedValues: Record<string, unknown> | null = null;
  let starting = false;
  let submitting = false;
  let requestingAssistance = false;
  let refreshingTrace = false;
  let errorMessage = '';
  let assistanceError = '';
  $: interaction = run?.interaction ?? null;
  $: interactionKey = `${run?.run_id ?? 'idle'}:${history.length}:${interaction?.id ?? 'terminal'}`;
  $: title = interaction?.content?.title || humanTitle(interaction?.id) || 'Service interaction';
  $: description = interaction?.content?.description;
  $: summaryData = interaction?.content?.data;

  async function start(): Promise<void> {
    starting = true;
    errorMessage = '';
    traceEvents = [];
    history = [];
    conversation = [];
    clearAssistance();
    try {
      run = await startJourney(JOURNEY_ID);
      rememberInteraction(run);
      await refreshTrace();
    } catch (error) {
      errorMessage = messageFrom(error);
    } finally {
      starting = false;
    }
  }

  async function requestAssistance(): Promise<void> {
    if (!run || !assistanceMessage.trim()) return;
    requestingAssistance = true;
    assistanceError = '';
    const message = assistanceMessage.trim();
    try {
      const response = await requestJourneyAssistance(run.run_id, message, conversation);
      assistance = response;
      proposedValues =
        response.action.type === 'propose_values' ? { ...response.action.values } : null;
      conversation = [
        ...conversation,
        { role: 'user', content: message },
        { role: 'assistant', content: assistantConversationMessage(response) }
      ];
      assistanceMessage = '';
      await refreshTrace();
    } catch (error) {
      assistanceError = messageFrom(error);
      await refreshTrace();
    } finally {
      requestingAssistance = false;
    }
  }

  async function submit(result: Record<string, unknown>): Promise<void> {
    if (!run) return;
    submitting = true;
    errorMessage = '';
    try {
      run = await submitJourneyResult(run.run_id, result);
      rememberInteraction(run);
      clearAssistance();
      await refreshTrace();
    } catch (error) {
      errorMessage = messageFrom(error);
      await refreshTrace();
    } finally {
      submitting = false;
    }
  }

  async function refreshTrace(): Promise<void> {
    if (!run) return;
    refreshingTrace = true;
    try {
      traceEvents = (await getJourneyTrace(run.run_id)).events;
    } catch (error) {
      if (!errorMessage) errorMessage = messageFrom(error);
    } finally {
      refreshingTrace = false;
    }
  }

  function rememberInteraction(response: JourneyRunResponse): void {
    const interactionId = response.interaction?.id;
    if (!interactionId) return;
    history = [
      ...history,
      { sequence: history.length + 1, interactionId, status: response.status }
    ];
  }

  function clearAssistance(): void {
    assistanceMessage = '';
    assistance = null;
    proposedValues = null;
    assistanceError = '';
  }

  function reset(): void {
    run = null;
    traceEvents = [];
    history = [];
    conversation = [];
    clearAssistance();
    errorMessage = '';
  }

  function assistantConversationMessage(response: AssistanceResponse): string {
    if (response.action.type === 'no_safe_suggestion') {
      return response.action.message ?? 'No safe values could be proposed.';
    }
    return `Proposed values: ${JSON.stringify(response.action.values)}`;
  }

  function humanTitle(value: string | undefined): string {
    return value
      ? value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
      : '';
  }

  function messageFrom(error: unknown): string {
    return error instanceof Error ? error.message : 'An unexpected error occurred';
  }
</script>

<svelte:head>
  <title>Journey executor prototype</title>
  <meta
    name="description"
    content="A developer-facing prototype of an agent-assisted, deterministic service journey"
  />
</svelte:head>
<header>
  <div class="header-inner">
    <div class="brand"><span aria-hidden="true">◆</span><strong>Agentic legibility</strong></div>
    <span class="prototype">Experimental prototype</span>
  </div>
</header>
<div class="phase">
  <div><strong>Research prototype</strong><span>This is not a live government service.</span></div>
</div>
<main>
  <div class="intro">
    <span class="eyebrow">Comparable journey execution spike</span>
    <h1>Change your driving-licence address</h1>
    <p>
      This demonstration shows an agent proposing values inside a deterministic journey.
      The service API still controls progression, while the developer panel exposes the
      application state and raw run trace.
    </p>
  </div>

  {#if errorMessage}
    <div class="error-banner" role="alert">
      <strong>There is a problem</strong><span>{errorMessage}</span>
    </div>
  {/if}
  <div class="layout">
    <section class="service-card" aria-live="polite">
      {#if !run}
        <div class="card-body">
          <span class="step-label">DVLA-like test journey</span>
          <h2>Start the service journey</h2>
          <p>
            The browser asks the Python executor to start the journey. The service returns
            the first interaction and controls every subsequent transition.
          </p>
          <ul>
            <li>Describe an answer or enter it directly</li>
            <li>Review any values proposed by the agent</li>
            <li>Confirm before completion</li>
          </ul>
          <button class="primary" type="button" onclick={start} disabled={starting}
            >{starting ? 'Starting journey…' : 'Start journey'}</button
          >
        </div>
      {:else if run.terminal}
        <div class="card-body completion">
          <div class="tick" aria-hidden="true">✓</div>
          <span class="step-label">Journey finished</span>
          <h2>Journey finished</h2>
          <p>
            The service returned a terminal status. No further action was selected by the
            agent, executor or browser.
          </p>
          <dl>
            <div><dt>Final status</dt><dd>{run.status}</dd></div>
            <div><dt>Interactions</dt><dd>{history.length}</dd></div>
            <div><dt>Trace events</dt><dd>{traceEvents.length}</dd></div>
          </dl>
          <button class="secondary" type="button" onclick={reset}>Start another run</button>
        </div>
      {:else if interaction}
        <div class="card-body">
          <div class="interaction-meta">
            <span class="step-label">Interaction {history.length}</span>
            <code>{interaction.id ?? 'unnamed_interaction'}</code>
          </div>
          <h2>{title}</h2>
          {#if description}<p>{description}</p>{/if}
          <DataSummary data={summaryData} />
          <AssistancePanel
            bind:message={assistanceMessage}
            response={assistance}
            error={assistanceError}
            disabled={submitting}
            requesting={requestingAssistance}
            onRequest={requestAssistance}
          />
          {#key interactionKey}
            <SchemaForm
              {interaction}
              {proposedValues}
              disabled={submitting || requestingAssistance}
              onSubmit={submit}
            />
          {/key}
        </div>
      {/if}
    </section>
    <DeveloperPanel
      {run}
      {traceEvents}
      {history}
      apiBaseUrl={API_BASE_URL}
      refreshing={refreshingTrace}
      onRefresh={refreshTrace}
    />
  </div>
</main>

<footer>
  <div>
    <strong>Agentic Legibility</strong
    ><span>Prototype for exploring server-driven journeys and comparable traces.</span>
  </div>
</footer>
<style>
  :global(*) { box-sizing: border-box; }
  :global(html) { font-family: Arial, Helvetica, sans-serif; color: #0b0c0c; background: #f3f2f1; }
  :global(body) { margin: 0; min-width: 20rem; font-size: 1rem; line-height: 1.5; }
  :global(button), :global(input), :global(select), :global(textarea) { font-family: inherit; }
  header { border-bottom: .35rem solid #1d70b8; background: #0b0c0c; color: #fff; }
  .header-inner, .phase > div, main, footer > div { width: min(100% - 2rem,88rem); margin: 0 auto; }
  .header-inner { display: flex; justify-content: space-between; align-items: center; min-height: 4rem; gap: 1rem; }
  .brand { display: flex; gap: .65rem; align-items: center; font-size: 1.2rem; }
  .brand span { color: #59cbe8; transform: rotate(45deg); }
  .prototype { border: 1px solid #b1b4b6; padding: .2rem .5rem; font-size: .78rem; font-weight: 700; }
  .phase { border-bottom: 1px solid #b1b4b6; background: #fff; }
  .phase > div { display: flex; gap: .7rem; align-items: center; min-height: 3rem; font-size: .9rem; }
  .phase strong { background: #1d70b8; color: #fff; padding: .1rem .45rem; text-transform: uppercase; }
  main { padding: 2.5rem 0 4rem; }
  .intro { max-width: 52rem; margin-bottom: 2rem; }
  .eyebrow, .step-label { color: #1d70b8; font-size: .78rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h1 { margin: .25rem 0 .6rem; font-size: clamp(2rem,4vw,3.25rem); line-height: 1.05; letter-spacing: -.035em; }
  .intro p, .card-body > p { color: #505a5f; font-size: 1.05rem; }
  .layout { display: grid; grid-template-columns: minmax(0,1.08fr) minmax(23rem,.92fr); gap: 1.5rem; align-items: start; }
  .service-card { min-height: 34rem; border: 1px solid #b1b4b6; border-top: .4rem solid #1d70b8; background: #fff; box-shadow: 0 .5rem 1.5rem rgb(11 12 12 / 8%); }
  .card-body { padding: clamp(1.5rem,5vw,3rem); }
  h2 { margin: .35rem 0 .8rem; font-size: clamp(1.55rem,3vw,2.15rem); line-height: 1.15; }
  .card-body ul { margin: 1.4rem 0 2rem; padding-left: 1.3rem; }
  .primary, .secondary { padding: .72rem 1.25rem; font: inherit; font-weight: 700; cursor: pointer; }
  .primary { border: 0; border-bottom: .2rem solid #002d18; background: #00703c; color: #fff; box-shadow: 0 .15rem 0 #002d18; }
  .secondary { border: 2px solid #0b0c0c; background: #fff; color: #0b0c0c; }
  .primary:focus, .secondary:focus { outline: .2rem solid #ffdd00; outline-offset: .15rem; }
  button:disabled { opacity: .55; cursor: wait; }
  .interaction-meta { display: flex; justify-content: space-between; gap: 1rem; align-items: center; }
  .interaction-meta code { max-width: 55%; background: #f3f2f1; padding: .2rem .45rem; color: #505a5f; font-size: .72rem; overflow-wrap: anywhere; }
  .completion { text-align: center; }
  .tick { display: grid; place-items: center; width: 4rem; height: 4rem; margin: 0 auto 1rem; border-radius: 50%; background: #00703c; color: #fff; font-size: 2.2rem; }
  .completion dl { max-width: 28rem; margin: 1.5rem auto 2rem; border-top: 1px solid #b1b4b6; text-align: left; }
  .completion dl div { display: grid; grid-template-columns: 1fr 1fr; padding: .65rem 0; border-bottom: 1px solid #b1b4b6; }
  .completion dt { font-weight: 700; }
  .completion dd { margin: 0; }
  .error-banner { display: grid; gap: .2rem; margin-bottom: 1.5rem; border: .3rem solid #d4351c; background: #fff; padding: 1rem 1.2rem; }
  footer { border-top: 1px solid #b1b4b6; background: #dee0e2; color: #505a5f; }
  footer > div { display: flex; justify-content: space-between; gap: 1rem; padding: 1.5rem 0; font-size: .85rem; }
  @media (max-width: 64rem) { .layout { grid-template-columns: 1fr; } }
  @media (max-width: 40rem) { .header-inner, .phase > div, footer > div { align-items: flex-start; flex-direction: column; justify-content: center; padding: .8rem 0; } .interaction-meta { align-items: flex-start; flex-direction: column; } .interaction-meta code { max-width: 100%; } }
</style>
