<script lang="ts">
  import { browser } from '$app/environment';
  import { replaceState } from '$app/navigation';
  import { page } from '$app/state';
  import { onDestroy } from 'svelte';
  import {
    DurableApiError,
    getAutonomy,
    getRunState,
    getWorkflowDefinition,
    listProfiles,
    resumeAutonomy,
    setAutonomy,
    submitRunInput
  } from '$lib/api/client';
  import { watchRun } from '$lib/api/sse';
  import { findProcessContaining } from '$lib/graph/run-to-graph';
  import RunGraph from '$lib/graph/RunGraph.svelte';
  import KindField from '$lib/components/forms/KindField.svelte';
  import PreseedField from '$lib/components/PreseedField.svelte';
  import type { PreseedExample } from '$lib/agentic/preseed-examples';
  import type { WorkflowDefinition } from '$lib/graph/fsm';
  import type { AutonomyPolicy, AwaitingInput, ProfileSummary, RunEvent } from '$lib/types';

  const workflowId = page.params.workflowId!;

  interface LogLine {
    category?: string;
    summary?: string;
  }

  let definition: WorkflowDefinition | null = $state(null);
  let loadError: string | null = $state(null);

  let status: string | null = $state(null);
  let currentStateId: string | null = $state(null);
  let processId = $derived(definition ? findProcessContaining(definition, currentStateId) : '');

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

  let profiles: ProfileSummary[] = $state([]);
  let profileFixture = $state(page.url.searchParams.get('profile') ?? '');
  let preseed = $state('');
  let autonomyLevel: AutonomyPolicy['autonomy_level'] = $state('balanced');
  let notifyCategories: string[] = $state(['identity', 'payment', 'irreversible']);
  let pauseBeforeExternalCall = $state(true);
  let continueAfterAnswer = $state(true);
  let hasSeed = $derived(!!profileFixture || !!preseed.trim());
  let policySaving = $state(false);
  let policyError: string | null = $state(null);

  let resuming = $state(false);
  let resumeError: string | null = $state(null);
  let resumeAbort: AbortController | null = null;

  let graphRef: RunGraph | undefined = $state(undefined);

  $effect(() => {
    getWorkflowDefinition(workflowId)
      .then((result) => (definition = result))
      .catch((error: unknown) => {
        loadError = error instanceof DurableApiError ? error.message : 'Failed to load workflow definition';
      });

    getRunState(workflowId)
      .then((state) => {
        status = state.status;
        currentStateId = state.awaiting?.state_id ?? null;
      })
      .catch(() => {
        // Non-fatal: the graph still renders from the definition alone, just without a highlight.
      });

    listProfiles()
      .then((result) => (profiles = result))
      .catch(() => {
        // Non-fatal: the policy panel just falls back to the profile carried in via the URL.
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

  function applyExample(example: PreseedExample) {
    autonomyLevel = example.policy.autonomy_level;
    notifyCategories = [...example.policy.notify_categories];
    profileFixture = '';
  }

  function describeValue(value: unknown): string {
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    return text.length > 60 ? `${text.slice(0, 57)}…` : text;
  }

  function handleEvent(event: RunEvent) {
    if (event.type === 'trace') {
      log = [...log, { category: event.category, summary: event.summary }];
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
    policySaving = true;
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
    } finally {
      policySaving = false;
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
            const detail = event.detail as { value?: unknown } | undefined;
            const summary =
              detail && 'value' in detail ? `${event.summary}: ${describeValue(detail.value)}` : event.summary;
            log = [...log, { category: event.category, summary }];
          } else if (event.type === 'escalation') {
            log = [...log, { category: event.category ?? 'AGENT', summary: event.summary }];
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
      currentStateId = state.awaiting?.state_id ?? null;
    } catch {
      // Best-effort refresh; the SSE feed will catch up if this fails.
    }
  }

  async function handleEscalationSubmit(value: unknown) {
    if (!escalation) return;
    try {
      await submitRunInput(workflowId, escalation.token, value);
      escalation = null;
      await refreshCurrentState();
      if (continueAfterAnswer && status !== 'COMPLETED') void resume();
    } catch (error) {
      resumeError = error instanceof DurableApiError ? error.message : 'Failed to submit input';
    }
  }
</script>

<h1 class="govuk-heading-l">Autonomous run {workflowId}</h1>

{#if loadError}
  <p class="govuk-error-message">{loadError}</p>
{/if}

{#if status}
  <p class="govuk-body">Status: <strong>{status}</strong></p>
{/if}

<div class="agentic-dashboard">
  <div class="agentic-dashboard__graph">
    {#if definition}
      <RunGraph bind:this={graphRef} {definition} {processId} {currentStateId} />
      <div class="agentic-dashboard__graph-controls">
        <button class="govuk-button govuk-button--secondary" type="button" onclick={() => graphRef?.fit()}>
          Fit
        </button>
        <button
          class="govuk-button govuk-button--secondary"
          type="button"
          onclick={() => graphRef?.zoomIn()}
        >
          Zoom in
        </button>
        <button
          class="govuk-button govuk-button--secondary"
          type="button"
          onclick={() => graphRef?.zoomOut()}
        >
          Zoom out
        </button>
      </div>
    {/if}
  </div>

  <div class="agentic-dashboard__panel">
    {#if escalationAwaiting}
      <div class="govuk-inset-text">
        <p class="govuk-body">
          The autonomous answerer escalated{escalation?.reason ? `: ${escalation.reason}` : '.'}
        </p>
        <KindField awaiting={escalationAwaiting} onsubmit={handleEscalationSubmit} />
        <div class="govuk-checkboxes govuk-checkboxes--small govuk-!-margin-top-2">
          <div class="govuk-checkboxes__item">
            <input
              class="govuk-checkboxes__input"
              id="continue-after-answer"
              type="checkbox"
              bind:checked={continueAfterAnswer}
            />
            <label class="govuk-label govuk-checkboxes__label" for="continue-after-answer">
              Carry on autonomously after I answer
            </label>
          </div>
        </div>
      </div>
    {:else}
      <div class="ss-panel govuk-!-margin-bottom-4">
        <h2 class="govuk-heading-m">Autonomy policy</h2>

        {#if policyError}
          <p class="govuk-error-message">{policyError}</p>
        {/if}

        <div class="govuk-form-group">
          <label class="govuk-label" for="profile">Profile bundle</label>
          <select class="govuk-select" id="profile" bind:value={profileFixture}>
            <option value="">None: use pre-seeded facts only</option>
            {#if profileFixture && !profiles.some((profile) => profile.fixture === profileFixture)}
              <option value={profileFixture}>{profileFixture}</option>
            {/if}
            {#each profiles as profile (profile.fixture)}
              <option value={profile.fixture}>{profile.title}</option>
            {/each}
          </select>
        </div>

        <PreseedField workflowId={definition?.id ?? ''} bind:value={preseed} onexample={applyExample} />

        <div class="govuk-form-group">
          <label class="govuk-label" for="autonomy-level">Autonomy level</label>
          <select class="govuk-select" id="autonomy-level" bind:value={autonomyLevel}>
            <option value="cautious">Cautious</option>
            <option value="balanced">Balanced</option>
            <option value="assertive">Assertive</option>
          </select>
        </div>

        <fieldset class="govuk-fieldset">
          <legend class="govuk-fieldset__legend govuk-fieldset__legend--s">Notify me on</legend>
          <div class="govuk-checkboxes govuk-checkboxes--small">
            {#each [['identity', 'Identity'], ['payment', 'Payment'], ['irreversible', 'Irreversible actions']] as [value, label] (value)}
              <div class="govuk-checkboxes__item">
                <input
                  class="govuk-checkboxes__input"
                  id="notify-{value}"
                  type="checkbox"
                  {value}
                  bind:group={notifyCategories}
                />
                <label class="govuk-label govuk-checkboxes__label" for="notify-{value}">{label}</label>
              </div>
            {/each}
          </div>
        </fieldset>

        <div class="govuk-checkboxes govuk-checkboxes--small">
          <div class="govuk-checkboxes__item">
            <input
              class="govuk-checkboxes__input"
              id="pause-before-external-call"
              type="checkbox"
              bind:checked={pauseBeforeExternalCall}
            />
            <label class="govuk-label govuk-checkboxes__label" for="pause-before-external-call">
              Pause before external calls
            </label>
          </div>
        </div>

        <button
          class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
          type="button"
          disabled={policySaving || !hasSeed}
          onclick={() => savePolicy()}
        >
          {policySaving ? 'Saving…' : 'Save policy'}
        </button>
      </div>

      <div class="ss-panel govuk-!-margin-bottom-4">
        <h2 class="govuk-heading-m">Run it</h2>

        {#if resumeError}
          <p class="govuk-error-message">{resumeError}</p>
        {/if}

        {#if resuming}
          <button class="govuk-button govuk-button--warning govuk-!-margin-bottom-0" type="button" onclick={stopResume}>
            Stop
          </button>
        {:else}
          <button class="govuk-button ss-cta govuk-!-margin-bottom-0" type="button" disabled={!hasSeed} onclick={resume}>
            Resume autonomously
          </button>
        {/if}
      </div>
    {/if}

    <h2 class="govuk-heading-m">Activity</h2>
    <div class="agentic-dashboard__log">
      {#each log as line, index (index)}
        <div class="ss-card agentic-dashboard__log-row">
          <span class="govuk-!-font-weight-bold">{line.category}</span>
          <span class="govuk-body-s govuk-!-margin-0">{line.summary}</span>
        </div>
      {:else}
        <p class="govuk-body-s ss-muted">No activity yet.</p>
      {/each}
    </div>
  </div>
</div>

<style>
  .agentic-dashboard {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
    gap: 20px;
    align-items: start;
  }

  .agentic-dashboard__graph {
    position: relative;
    height: 70vh;
    border: 1px solid #b1b4b6;
  }

  .agentic-dashboard__graph-controls {
    position: absolute;
    top: 10px;
    right: 10px;
    display: flex;
    gap: 8px;
  }

  .agentic-dashboard__log {
    max-height: 240px;
    overflow-y: auto;
    border: 1px solid #b1b4b6;
  }

  .agentic-dashboard__log-row {
    gap: 10px;
  }
</style>
