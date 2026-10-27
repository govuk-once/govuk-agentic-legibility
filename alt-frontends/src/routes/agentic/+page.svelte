<script lang="ts">
  import { goto } from '$app/navigation';
  import { DurableApiError, listProfiles, listWorkflows, setAutonomy, startRun } from '$lib/api/client';
  import type { PreseedExample } from '$lib/agentic/preseed-examples';
  import AgentCard from '$lib/components/agentic/AgentCard.svelte';
  import AgentFactsField from '$lib/components/agentic/AgentFactsField.svelte';
  import AgentRunSummaryCard from '$lib/components/agentic/AgentRunSummaryCard.svelte';
  import AgentWidePage from '$lib/components/agentic/AgentWidePage.svelte';
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

  // The choices made so far, as rows for the run summary.
  const askLabels: Record<string, string> = {
    identity: 'Identity',
    payment: 'Payment',
    irreversible: 'Irreversible actions'
  };
  const factLines = $derived(preseed.split('\n').filter((line) => line.trim() !== '').length);
  const summaryDetails = $derived([
    { label: 'Workflow', value: workflows.find((workflow) => workflow.id === selectedWorkflowId)?.name ?? '' },
    {
      label: 'Profile bundle',
      value: profiles.find((profile) => profile.fixture === selectedProfileFixture)?.title ?? 'None'
    },
    { label: 'Facts', value: factLines === 0 ? 'None' : factLines === 1 ? '1 line' : `${factLines} lines` },
    { label: 'Autonomy', value: autonomyLevel.charAt(0).toUpperCase() + autonomyLevel.slice(1) },
    {
      label: 'Ask before',
      value: notifyCategories.length === 0 ? 'Nothing selected' : notifyCategories.map((value) => askLabels[value] ?? value).join(', ')
    }
  ]);

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

<AgentWidePage>
  <h1 class="govuk-visually-hidden">Start an autonomous run</h1>

  {#if loadError}
    <p class="govuk-error-message">{loadError}</p>
  {/if}

  {#if startError}
    <p class="govuk-error-message">{startError}</p>
  {/if}

  <div class="agent-page__columns">
    <AgentCard title="Facts for this run">
      {#snippet aside()}
        <label class="govuk-visually-hidden" for="workflow">Journey</label>
        <select class="govuk-select agent-page__journey" id="workflow" bind:value={selectedWorkflowId}>
          {#each workflows as workflow (workflow.id)}
            <option value={workflow.id}>{workflow.name ?? workflow.id}</option>
          {/each}
        </select>
      {/snippet}

      <div class="govuk-form-group">
        <label class="govuk-label govuk-label--s" for="profile">Profile bundle</label>
        <div id="profile-hint" class="govuk-hint govuk-!-font-size-16">
          A bundle gives the agent a ready-made set of answers. Choose one or leave it empty.
        </div>
        <select class="govuk-select" id="profile" aria-describedby="profile-hint" bind:value={selectedProfileFixture}>
          <option value="">None: use pre-seeded facts only</option>
          {#each profiles as profile (profile.fixture)}
            <option value={profile.fixture}>{profile.title}</option>
          {/each}
        </select>
      </div>

      <AgentFactsField workflowId={selectedWorkflowId} bind:value={preseed} onexample={applyExample} />
    </AgentCard>

    <div class="agent-page__side">
      <AgentCard title="Agent control">
        <div class="govuk-form-group">
          <label class="govuk-label govuk-label--s" for="autonomy-level">Autonomy level</label>
          <select class="govuk-select agent-page__full-width" id="autonomy-level" bind:value={autonomyLevel}>
            <option value="cautious">Cautious &mdash; escalates readily</option>
            <option value="balanced">Balanced</option>
            <option value="assertive">Assertive &mdash; infers readily</option>
          </select>
        </div>

        <fieldset class="govuk-fieldset">
          <legend class="govuk-fieldset__legend govuk-fieldset__legend--s">Ask me before answering</legend>
          <div class="govuk-checkboxes govuk-checkboxes--small agent-chips">
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
      </AgentCard>

      <AgentRunSummaryCard
        details={summaryDetails}
        bind:runImmediately
        {starting}
        {canStart}
        onstart={start}
      />
    </div>
  </div>
</AgentWidePage>

<style>
  /* The journey drop-down in the card header is smaller than a normal one. */
  .agent-page__journey {
    min-width: 0;
    max-width: 260px;
    height: 36px;
  }

  .agent-page__full-width {
    width: 100%;
  }

  /* The cards on the right are stacked with a gap between them. */
  .agent-page__side {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  /* The "Ask me before answering" choices are set a little smaller than the other text so all
     three fit side by side. They drop to a second line if the window is too narrow. */
  .agent-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0 12px;
  }

  .agent-chips :global(.govuk-checkboxes__item) {
    float: none;
    margin: 0;
  }

  .agent-chips :global(.govuk-checkboxes__label) {
    max-width: none;
    padding-right: 8px;
    font-size: 1rem;
    white-space: nowrap;
  }

  /* The cards sit in two columns: the facts on the left, and the agent's controls on the right. */
  .agent-page__columns {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 450px;
    gap: 40px;
    align-items: start;
  }

  @media (max-width: 64em) {
    .agent-page__columns {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
