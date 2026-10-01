<script lang="ts">
  import { goto } from '$app/navigation';
  import { DurableApiError, listProfiles, listWorkflows, setAutonomy, startRun } from '$lib/api/client';
  import type { PreseedExample } from '$lib/agentic/preseed-examples';
  import PreseedField from '$lib/components/PreseedField.svelte';
  import type { AutonomyPolicy, ProfileSummary, WorkflowSummary } from '$lib/types';

  let workflows: WorkflowSummary[] = $state([]);
  let profiles: ProfileSummary[] = $state([]);
  let loadError: string | null = $state(null);

  let selectedWorkflowId = $state('');
  let selectedProfileFixture = $state('');
  let autonomyLevel: AutonomyPolicy['autonomy_level'] = $state('balanced');
  let notifyCategories: string[] = $state(['identity', 'payment', 'irreversible']);
  let preseed = $state('');
  let runImmediately = $state(true);

  let starting = $state(false);
  let startError: string | null = $state(null);

  let canStart = $derived(!!selectedWorkflowId && (!!selectedProfileFixture || !!preseed.trim()));

  $effect(() => {
    Promise.all([listWorkflows(), listProfiles()])
      .then(([workflowResult, profileResult]) => {
        workflows = workflowResult;
        profiles = profileResult;
        selectedWorkflowId ||= workflowResult[0]?.id ?? '';
        selectedProfileFixture ||= profileResult[0]?.fixture ?? '';
      })
      .catch((error: unknown) => {
        loadError = error instanceof DurableApiError ? error.message : 'Failed to load workflows/profiles';
      });
  });

  // Examples are self-contained, so drop the profile bundle rather than mix in
  // a scenario whose facts could contradict them.
  function applyExample(example: PreseedExample) {
    autonomyLevel = example.policy.autonomy_level;
    notifyCategories = [...example.policy.notify_categories];
    selectedProfileFixture = '';
  }

  async function start() {
    if (!canStart) return;
    startError = null;
    starting = true;
    try {
      const { workflow_id } = await startRun(selectedWorkflowId);
      await setAutonomy(workflow_id, {
        policy: {
          autonomy_level: autonomyLevel,
          notify_categories: notifyCategories,
          pause_before_external_call: true
        },
        profile_fixture: selectedProfileFixture,
        preseed
      });
      const query = new URLSearchParams();
      if (selectedProfileFixture) query.set('profile', selectedProfileFixture);
      if (runImmediately) query.set('autorun', '1');
      await goto(`/agentic/${encodeURIComponent(workflow_id)}?${query}`);
    } catch (error) {
      startError = error instanceof DurableApiError ? error.message : 'Failed to start run';
    } finally {
      starting = false;
    }
  }
</script>

<h1 class="govuk-heading-l">Start an autonomous run</h1>

<p class="govuk-body">
  Seed a run with a profile bundle, facts of your own, or both, and let the autonomous answerer drive it. It
  escalates to a human only when it can't confidently resolve a field, or the field is in a category you've
  asked to be told about.
</p>

{#if loadError}
  <p class="govuk-error-message">{loadError}</p>
{/if}

{#if startError}
  <p class="govuk-error-message">{startError}</p>
{/if}

<div class="ss-panel govuk-!-margin-top-4">
  <div class="govuk-form-group">
    <label class="govuk-label" for="workflow">Workflow</label>
    <select class="govuk-select" id="workflow" bind:value={selectedWorkflowId}>
      {#each workflows as workflow (workflow.id)}
        <option value={workflow.id}>{workflow.name ?? workflow.id}</option>
      {/each}
    </select>
  </div>

  <div class="govuk-form-group">
    <label class="govuk-label" for="profile">Profile bundle</label>
    <select class="govuk-select" id="profile" bind:value={selectedProfileFixture}>
      <option value="">None: use pre-seeded facts only</option>
      {#each profiles as profile (profile.fixture)}
        <option value={profile.fixture}>{profile.title}</option>
      {/each}
    </select>
  </div>

  <PreseedField workflowId={selectedWorkflowId} bind:value={preseed} onexample={applyExample} />

  <div class="govuk-form-group">
    <label class="govuk-label" for="autonomy-level">Autonomy level</label>
    <select class="govuk-select" id="autonomy-level" bind:value={autonomyLevel}>
      <option value="cautious">Cautious &mdash; escalates readily</option>
      <option value="balanced">Balanced</option>
      <option value="assertive">Assertive &mdash; infers readily</option>
    </select>
  </div>

  <fieldset class="govuk-fieldset govuk-!-margin-bottom-4">
    <legend class="govuk-fieldset__legend govuk-fieldset__legend--s">Ask me before answering</legend>
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
      <input class="govuk-checkboxes__input" id="run-immediately" type="checkbox" bind:checked={runImmediately} />
      <label class="govuk-label govuk-checkboxes__label" for="run-immediately">
        Start answering straight away
      </label>
    </div>
  </div>
</div>

<button class="govuk-button ss-cta govuk-!-margin-top-4" type="button" disabled={starting || !canStart} onclick={start}>
  {starting ? 'Starting…' : 'Start'}
</button>
