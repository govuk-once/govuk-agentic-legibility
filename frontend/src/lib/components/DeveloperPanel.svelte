<script lang="ts">
  import type { JourneyHistoryItem, JourneyRunResponse, TraceEvent } from '$lib/types';

  export let run: JourneyRunResponse | null;
  export let traceEvents: TraceEvent[];
  export let history: JourneyHistoryItem[];
  export let apiBaseUrl: string;
  export let refreshing = false;
  export let onRefresh: () => void;

  type Tab = 'state' | 'trace' | 'architecture';
  let activeTab: Tab = 'state';
  $: latestServiceResponse = findLatestEventValue(traceEvents, 'http_exchange', 'response');
  $: latestAgentInvocation = findLatestEvent(traceEvents, 'agent_invoked');
  $: latestAgentResponse = findLatestAgentEvent(traceEvents);

  function json(value: unknown): string {
    return JSON.stringify(value, null, 2);
  }

  function findLatestEvent(events: TraceEvent[], type: string): TraceEvent | null {
    return [...events].reverse().find((event) => event.type === type) ?? null;
  }

  function findLatestEventValue(
    events: TraceEvent[],
    type: string,
    field: string
  ): unknown {
    const event = findLatestEvent(events, type);
    if (!event) return null;
    const value = event[field];
    if (type === 'http_exchange' && field === 'response') {
      if (typeof value === 'object' && value !== null && 'body' in value) {
        return (value as { body: unknown }).body;
      }
    }
    return value ?? null;
  }

  function findLatestAgentEvent(events: TraceEvent[]): TraceEvent | null {
    return (
      [...events]
        .reverse()
        .find((event) => event.type === 'agent_responded' || event.type === 'agent_failed') ??
      null
    );
  }

  function eventTitle(event: TraceEvent, index: number): string {
    const sequence = typeof event.sequence === 'number' ? event.sequence : index;
    if (
      event.type === 'http_exchange' &&
      typeof event.request === 'object' &&
      event.request !== null
    ) {
      const request = event.request as { method?: unknown; path?: unknown };
      return `${sequence}. ${String(request.method ?? '')} ${String(request.path ?? '')}`.trim();
    }
    if (
      event.type === 'agent_responded' &&
      typeof event.action === 'object' &&
      event.action !== null
    ) {
      const action = event.action as { type?: unknown };
      return `${sequence}. agent ${String(action.type ?? 'responded')}`;
    }
    return `${sequence}. ${String(event.type ?? 'event')}`;
  }
</script>

<aside class="panel" aria-label="Developer view">
  <div class="heading">
    <div><span class="eyebrow">Developer view</span><h2>Under the hood</h2></div>
    <span class="connection"><i></i>{apiBaseUrl}</span>
  </div>
  <div class="tabs" role="tablist" aria-label="Developer information">
    <button
      type="button"
      role="tab"
      aria-selected={activeTab === 'state'}
      class:active={activeTab === 'state'}
      onclick={() => (activeTab = 'state')}>State</button
    >
    <button
      type="button"
      role="tab"
      aria-selected={activeTab === 'trace'}
      class:active={activeTab === 'trace'}
      onclick={() => (activeTab = 'trace')}>Raw trace ({traceEvents.length})</button
    >
    <button
      type="button"
      role="tab"
      aria-selected={activeTab === 'architecture'}
      class:active={activeTab === 'architecture'}
      onclick={() => (activeTab = 'architecture')}>Architecture</button
    >
  </div>
  <div class="body">
    {#if activeTab === 'state'}
      <section>
        <h3>Frontend-facing run</h3>
        {#if run}
          <dl class="metadata">
            <div><dt>Run</dt><dd>{run.run_id}</dd></div>
            <div><dt>Status</dt><dd>{run.status}</dd></div>
            <div><dt>Terminal</dt><dd>{run.terminal ? 'Yes' : 'No'}</dd></div>
          </dl>
          <pre>{json(run)}</pre>
        {:else}<p class="empty">Start a journey to inspect the state returned to the browser.</p>{/if}
      </section>
      <section>
        <h3>Latest agent invocation</h3>
        {#if latestAgentInvocation}
          <p class="note">
            The application supplies only conversation context and the current interaction.
            It does not give the agent a continuation token or next operation.
          </p>
          <pre>{json(latestAgentInvocation)}</pre>
        {:else}<p class="empty">Ask for a suggestion to inspect the model input.</p>{/if}
      </section>
      <section>
        <h3>Latest agent result</h3>
        {#if latestAgentResponse}
          <pre>{json(latestAgentResponse)}</pre>
        {:else}<p class="empty">No agent response has been recorded yet.</p>{/if}
      </section>
      <section>
        <h3>Service-selected interactions</h3>
        {#if history.length > 0}
          <ol class="history">
            {#each history as item, index}
              <li>
                <span>{item.interactionId}</span><small>{item.status}</small>
                {#if index < history.length - 1}<b aria-hidden="true">↓</b>{/if}
              </li>
            {/each}
          </ol>
        {:else}<p class="empty">No interactions have been returned yet.</p>{/if}
      </section>
      <section>
        <h3>Latest journey-service response</h3>
        {#if latestServiceResponse}
          <p class="note">Extracted from the HTTP trace. Continuation tokens are redacted.</p>
          <pre>{json(latestServiceResponse)}</pre>
        {:else}<p class="empty">No journey-service response has been traced yet.</p>{/if}
      </section>
    {:else if activeTab === 'trace'}
      <div class="trace-toolbar">
        <p>
          Ordered application and transport events recorded in the run's local JSONL file.
        </p>
        <button type="button" onclick={onRefresh} disabled={!run || refreshing}
          >{refreshing ? 'Refreshing…' : 'Refresh'}</button
        >
      </div>
      {#if traceEvents.length > 0}
        {#each traceEvents as event, index}
          <details open={index === traceEvents.length - 1}>
            <summary>{eventTitle(event, index)}</summary><pre>{json(event)}</pre>
          </details>
        {/each}
      {:else}<p class="empty">The trace will appear here after a journey starts.</p>{/if}
    {:else}
      <section>
        <h3>Control boundary</h3>
        <p class="note">
          The agent proposes values for one current interaction. The user reviews them;
          only the deterministic executor can follow the operation advertised by the
          journey service.
        </p>
        <div class="architecture" aria-label="Agent-assisted journey execution architecture">
          <div class="node browser">
            <strong>SvelteKit</strong><span>Collect natural language or direct form values</span>
          </div>
          <div class="split" aria-hidden="true">↓</div>
          <div class="node agent">
            <strong>Interaction assistant</strong
            ><span>Return propose_values or no_safe_suggestion</span>
          </div>
          <div class="arrow"><span>structured proposal</span>↓</div>
          <div class="node review">
            <strong>User review</strong><span>Accept, edit or ignore the proposed values</span>
          </div>
          <div class="arrow"><span>run ID + reviewed result</span>↓</div>
          <div class="node executor">
            <strong>Deterministic executor</strong><span>Follow the advertised operation</span>
          </div>
          <div class="arrow"><span>token + result</span>↓</div>
          <div class="node service">
            <strong>Journey service</strong><span>Validate, branch and return interaction</span>
          </div>
        </div>
      </section>
    {/if}
  </div>
</aside>
<style>
  .panel { position: sticky; top: 1rem; max-height: calc(100vh - 2rem); border: 1px solid #b1b4b6; border-radius: .5rem; background: #fff; color: #0b0c0c; overflow: hidden; box-shadow: 0 .5rem 1.5rem rgb(11 12 12 / 8%); }
  .heading { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; padding: 1rem 1.1rem; border-bottom: 1px solid #b1b4b6; background: #f3f2f1; }
  .eyebrow { color: #1d70b8; font-size: .72rem; font-weight: 800; letter-spacing: .11em; text-transform: uppercase; }
  h2 { margin: .18rem 0 0; font-size: 1.25rem; }
  .connection { display: flex; align-items: center; gap: .35rem; max-width: 13rem; color: #505a5f; font-family: ui-monospace, monospace; font-size: .67rem; overflow-wrap: anywhere; }
  .connection i { flex: 0 0 auto; width: .5rem; height: .5rem; border-radius: 50%; background: #00703c; }
  .tabs { display: flex; border-bottom: 1px solid #b1b4b6; background: #fff; overflow-x: auto; }
  .tabs button { border: 0; border-bottom: .18rem solid transparent; background: transparent; color: #505a5f; padding: .75rem .85rem .62rem; font: inherit; font-size: .78rem; font-weight: 700; white-space: nowrap; cursor: pointer; }
  .tabs button.active { border-bottom-color: #1d70b8; color: #0b0c0c; }
  .tabs button:hover { background: #f3f2f1; }
  .tabs button:focus, .trace-toolbar button:focus { outline: .18rem solid #ffdd00; outline-offset: -.18rem; }
  .body { max-height: calc(100vh - 9rem); padding: 1rem 1.1rem 1.5rem; overflow-y: auto; }
  section + section { margin-top: 1.5rem; padding-top: 1.2rem; border-top: 1px solid #b1b4b6; }
  h3 { margin: 0 0 .65rem; font-size: .9rem; }
  .metadata { margin: 0 0 .75rem; font-size: .75rem; }
  .metadata div { display: grid; grid-template-columns: 4rem minmax(0,1fr); gap: .5rem; margin-bottom: .3rem; }
  dt { color: #505a5f; }
  dd { margin: 0; font-family: ui-monospace, monospace; overflow-wrap: anywhere; }
  pre { margin: 0; border: 1px solid #b1b4b6; border-radius: .3rem; background: #f3f2f1; color: #0b0c0c; padding: .75rem; font-family: ui-monospace, monospace; font-size: .68rem; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
  .empty, .note, .trace-toolbar p { margin: 0 0 .75rem; color: #505a5f; font-size: .78rem; line-height: 1.5; }
  .history { margin: 0; padding: 0; list-style: none; }
  .history li { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: .2rem .6rem; position: relative; padding: .55rem .65rem; border: 1px solid #b1b4b6; background: #f8f8f8; font-family: ui-monospace, monospace; font-size: .72rem; }
  .history li + li { margin-top: 1.25rem; }
  .history small { color: #1d70b8; }
  .history b { position: absolute; bottom: -1.15rem; left: 50%; color: #1d70b8; }
  .trace-toolbar { display: flex; justify-content: space-between; gap: .75rem; align-items: flex-start; margin-bottom: .8rem; }
  .trace-toolbar button { border: 2px solid #0b0c0c; background: #fff; color: #0b0c0c; padding: .3rem .6rem; font: inherit; font-size: .72rem; font-weight: 700; cursor: pointer; }
  .trace-toolbar button:hover { background: #f3f2f1; }
  details { border: 1px solid #b1b4b6; background: #fff; }
  details + details { margin-top: .55rem; }
  summary { padding: .65rem .75rem; color: #0b0c0c; font-family: ui-monospace, monospace; font-size: .7rem; cursor: pointer; }
  details[open] summary { background: #f3f2f1; }
  details pre { border: 0; border-top: 1px solid #b1b4b6; border-radius: 0; }
  .architecture { display: flex; flex-direction: column; gap: .35rem; }
  .node { border: 1px solid #b1b4b6; border-left: .25rem solid #1d70b8; background: #f8f8f8; padding: .7rem .8rem; }
  .node.agent { border-left-color: #4c2c92; }
  .node.review { border-left-color: #1d70b8; }
  .node.executor { border-left-color: #f47738; }
  .node.service { border-left-color: #00703c; }
  .node strong, .node span { display: block; }
  .node strong { margin-bottom: .2rem; font-size: .82rem; }
  .node span { color: #505a5f; font-size: .7rem; }
  .arrow, .split { color: #1d70b8; text-align: center; }
  .arrow { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; }
  .arrow span { grid-column: 1; justify-self: end; margin-right: .6rem; color: #505a5f; font-family: ui-monospace, monospace; font-size: .63rem; }
  @media (max-width: 64rem) { .panel { position: static; max-height: none; } .body { max-height: none; } }
</style>
