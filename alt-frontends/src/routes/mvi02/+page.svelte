<script lang="ts">
  import { goto } from '$app/navigation';
  // Shared (src/lib/api/client.ts): lists the journeys, starts a run, and saves the agent's settings and facts
  import { DurableApiError, getWorkflowDefinition, listWorkflows, saveWebContext, setAutonomy, startRun } from '$lib/api/client';
  // Shared (src/lib/types.ts): the journey summary and agent policy types
  import type { AutonomyPolicy, WorkflowSummary } from '$lib/types';
  import { checkNeeds, needsFromDefinition, type Need, type NeedCheck } from '$lib/mvi02/needs';
  import FactsPanel from '$lib/mvi02/FactsPanel.svelte';
  import Icon from '$lib/mvi02/Icon.svelte';
  import Phone from '$lib/mvi02/Phone.svelte';
  import RadioCard from '$lib/mvi02/RadioCard.svelte';
  import ServiceCard from '$lib/mvi02/ServiceCard.svelte';
  import Switch from '$lib/mvi02/Switch.svelte';

  // Shared (src/lib/mvi/format.ts): splits a journey id into its department and name
  import { describeWorkflow } from '$lib/mvi/format';

  type View = 'journey' | 'settings' | 'overview';

  let view: View = $state('journey');
  let workflows: WorkflowSummary[] = $state([]);
  let selectedId = $state('');
  let loadError: string | null = $state(null);
  let startError: string | null = $state(null);
  let starting = $state(false);

  // The facts. They are typed in the composer or the side panel and handed over when the call starts.
  let notes = $state('');
  let draft = $state('');
  let lastAdded = $state('');
  let panelOpen = $state(false);

  // The agent's settings, the same ones /agentic has.
  let useAgent = $state(true);
  let autonomyLevel: AutonomyPolicy['autonomy_level'] = $state('balanced');
  let notifyCategories: string[] = $state(['identity', 'payment', 'irreversible']);
  let autorun = $state(false);

  // The icon and the time on each card. The journeys don't say how long they take, so these are
  // made up from the journey's id until they do.
  const tiles = ['#E4F7FD', '#EBD9FF', '#DEE2F7', '#DCEFE5'];

  function cardFor(workflow: WorkflowSummary): {
    icon: 'home' | 'home-plus' | 'heart' | 'passport';
    minutes: number;
    label: string;
  } {
    const id = `${workflow.id} ${workflow.name ?? ''}`.toLowerCase();
    if (id.includes('maternity')) return { icon: 'heart', minutes: 15, label: 'Claim maternity allowance' };
    if (id.includes('advanced')) {
      return { icon: 'home-plus', minutes: 10, label: 'Change your driving licence address advanced' };
    }
    return { icon: 'home', minutes: 5, label: 'Change your driving licence address' };
  }

  // What the chosen journey needs and how the facts stand on each, worked out on the overview.
  let needs: Need[] = $state([]);
  let checks: Record<string, NeedCheck> = $state({});
  let needsLoading = $state(false);

  // A need that is settled as "none" isn't something the caller has to get ready, so it isn't counted.
  const countable = $derived(needs.filter((need) => !need.fixed));
  const readyCount = $derived(
    countable.filter((need) => ['have', 'not_needed'].includes(checks[need.key]?.status ?? 'unknown')).length
  );

  // Reads the journey and checks it against the facts each time the overview opens or either changes.
  $effect(() => {
    if (view !== 'overview' || !selectedId) return;
    const id = selectedId;
    const facts = notes;
    let current = true;
    needsLoading = true;
    getWorkflowDefinition(id)
      .then(async (definition) => {
        const found = needsFromDefinition(definition);
        if (current) needs = found;
        const result = await checkNeeds(facts, found);
        if (current) checks = result;
      })
      .catch(() => {
        if (current) needs = [];
      })
      .finally(() => {
        if (current) needsLoading = false;
      });
    return () => {
      current = false;
    };
  });

  const askCategories: Array<[string, string]> = [
    ['identity', 'Identity'],
    ['payment', 'Payment'],
    ['irreversible', 'Irreversible actions']
  ];

  const levels: Array<[AutonomyPolicy['autonomy_level'], string, string]> = [
    ['cautious', 'Cautious', 'Escalates readily'],
    ['balanced', 'Balanced', 'A mix of both'],
    ['assertive', 'Assertive', 'Infers readily']
  ];

  const selected = $derived(workflows.find((workflow) => workflow.id === selectedId));
  const factCount = $derived(notes.split('\n').filter((line) => line.trim() !== '').length);

  $effect(() => {
    listWorkflows()
      .then((result) => {
        workflows = result;
        if (!selectedId && result.length > 0) selectedId = result[0].id;
      })
      .catch((error: unknown) => {
        loadError = error instanceof DurableApiError ? error.message : 'Failed to load workflows';
      });
  });

  function addContext(event: SubmitEvent) {
    event.preventDefault();
    const line = draft.trim();
    if (!line) return;
    notes = notes.trim() ? `${notes.trimEnd()}\n- ${line}` : `- ${line}`;
    lastAdded = line;
    draft = '';
  }

  function toggleCategory(value: string, on: boolean) {
    notifyCategories = on ? [...notifyCategories, value] : notifyCategories.filter((category) => category !== value);
  }

  async function startCall() {
    if (!selectedId || starting) return;
    startError = null;
    starting = true;
    try {
      const { workflow_id } = await startRun(selectedId);
      if (useAgent) {
        await setAutonomy(workflow_id, {
          policy: {
            autonomy_level: autonomyLevel,
            notify_categories: notifyCategories,
            pause_before_external_call: true
          },
          profile_fixture: '',
          // The agent needs something to read, so with no facts it is told so and asks the caller instead.
          preseed: notes.trim() || 'The caller has not provided any facts up front.'
        });
      } else if (notes.trim()) {
        try {
          await saveWebContext(workflow_id, notes);
        } catch {
          // Suggestions are optional, so the call still starts without them.
        }
      }
      const query = new URLSearchParams({ agent: useAgent ? '1' : '0', auto: autorun ? '1' : '0' });
      await goto(`/mvi02/${encodeURIComponent(workflow_id)}?${query}`);
    } catch (error) {
      startError = error instanceof DurableApiError ? error.message : 'Failed to start the call';
    } finally {
      starting = false;
    }
  }
</script>

<Phone pill={view === 'overview' ? { label: 'Ready', time: 'about 5 min', state: 'live' } : undefined}>
  {#if view === 'journey'}
    <div class="mvi2-screen">
      <h1 class="mvi2-title mvi2-title--home">Select your service</h1>

      {#if loadError}
        <p class="mvi2-error">{loadError}</p>
      {/if}

      <div class="mvi2-services" role="radiogroup" aria-label="Service">
        {#each workflows as workflow, index (workflow.id)}
          {@const card = cardFor(workflow)}
          <ServiceCard
            name="mvi2-journey"
            value={workflow.id}
            bind:group={selectedId}
            label={card.label}
            department={describeWorkflow(workflow.id).department}
            icon={card.icon}
            minutes={card.minutes}
            tile={tiles[index % tiles.length]}
          />
        {/each}
        <!-- There is no passport journey yet, so this card only holds its place. -->
        <ServiceCard
          name="mvi2-journey"
          value="passport-placeholder"
          group=""
          label="Renew your passport"
          department="HMPO"
          icon="passport"
          minutes={5}
          tile={tiles[3]}
          disabled
        />
      </div>
      <div class="mvi2-spacer"></div>
    </div>

    <div class="mvi2-composer">
      <div class="mvi2-bubble">
        <Icon name="logo" width={22} height={14} />
        <span>
          {#if lastAdded}
            Added. {factCount === 1 ? '1 fact' : `${factCount} facts`} so far. Anything else?
          {:else}
            Anything the service should know before we start?
          {/if}
        </span>
      </div>
      <button type="button" class="mvi2-chip" onclick={() => (panelOpen = true)}>
        <Icon name="person" />
        Load facts about you
        <Icon name="chevron" color="#02064A" />
      </button>
      <form class="mvi2-compose-row" onsubmit={addContext}>
        <input class="mvi2-input" type="text" placeholder="Add context" aria-label="Add context" bind:value={draft} />
        <button type="submit" class="mvi2-send" aria-label="Add" disabled={!draft.trim()}>
          <Icon name="send" />
        </button>
      </form>
    </div>

    <div class="mvi2-actions">
      <button
        type="button"
        class="mvi2-btn mvi2-btn--go"
        disabled={!selectedId}
        onclick={() => (view = 'settings')}
      >
        Start now
        <Icon name="arrow" color="#FFFFFF" />
      </button>
    </div>
  {:else if view === 'settings'}
    <div class="mvi2-screen">
      <button type="button" class="mvi2-chip" onclick={() => (view = 'journey')}>Back</button>
      <h1 class="mvi2-title">Agent settings</h1>

      <div class="mvi2-row">
        <span>Use an agent for this journey</span>
        <Switch bind:checked={useAgent} label="Use an agent for this journey" />
      </div>

      <div class="mvi2-stack" class:mvi2-dim={!useAgent}>
        <h2 class="mvi2-section" id="mvi2-autonomy-label">Autonomy level</h2>
        <div class="mvi2-stack" role="radiogroup" aria-labelledby="mvi2-autonomy-label">
          {#each levels as [value, label, hint] (value)}
            <RadioCard
              name="mvi2-autonomy"
              {value}
              bind:group={autonomyLevel}
              {label}
              {hint}
              size="small"
              disabled={!useAgent}
            />
          {/each}
        </div>

        <h2 class="mvi2-section">Ask me before answering</h2>
        <div class="mvi2-group">
          {#each askCategories as [value, label] (value)}
            <div class="mvi2-group__row">
              <span>{label}</span>
              <Switch
                checked={notifyCategories.includes(value)}
                {label}
                disabled={!useAgent}
                onchange={(on) => toggleCategory(value, on)}
              />
            </div>
          {/each}
        </div>
      </div>

      <div class="mvi2-row" class:mvi2-dim={!useAgent}>
        <span>Start answering straight away</span>
        <Switch bind:checked={autorun} label="Start answering straight away" disabled={!useAgent} />
      </div>
      <div class="mvi2-spacer"></div>
    </div>

    <div class="mvi2-actions">
      <button type="button" class="mvi2-btn" onclick={() => (view = 'overview')}>
        Continue
        <Icon name="arrow" color="#12E2F7" />
      </button>
    </div>
  {:else}
    <div class="mvi2-screen">
      <button type="button" class="mvi2-chip" onclick={() => (view = 'settings')}>Back</button>
      <div class="mvi2-stack">
        <h1 class="mvi2-title mvi2-title--lg">{selected?.name ?? 'Your journey'}</h1>
        <p class="mvi2-sub mvi2-sub--tight">A quick look before we start.</p>
      </div>

      <!-- Still a mock-up: nothing checks whether the service can be done online. -->
      <div class="mvi2-hero">
        <div class="mvi2-hero__head">
          <Icon name="check-circle" width={52} height={52} />
          <h2>You can do this online</h2>
        </div>
        <p>You can finish this on the call.</p>
      </div>

      <div class="mvi2-section__row">
        <h2>What this needs</h2>
        {#if countable.length > 0}
          <span>{readyCount} of {countable.length} ready</span>
        {/if}
      </div>
      <div class="mvi2-needs">
        {#each needs as need (need.key)}
          {@const check = checks[need.key]}
          {@const ready = check?.status === 'have' || check?.status === 'not_needed'}
          <div class="mvi2-need" class:mvi2-need--ready={ready} class:mvi2-need--none={need.fixed === 'none'}>
            {#if ready}
              <Icon name="check-circle" />
            {:else if need.kind === 'address' && !need.fixed}
              <Icon name="logo" width={28} height={17} />
            {:else}
              <Icon name="circle" />
            {/if}
            <div>
              <strong>{need.label}</strong>
              <span>
                {#if need.fixed === 'none'}
                  Not needed
                {:else if check?.status === 'have'}
                  We have it
                {:else if check?.status === 'not_needed'}
                  Not needed
                {:else if needsLoading}
                  Checking your facts…
                {:else if need.kind === 'address'}
                  I'll check it with you
                {:else if need.kind === 'detail'}
                  I'll ask you
                {:else}
                  May be needed
                {/if}
              </span>
            </div>
          </div>
        {:else}
          <p class="mvi2-sub">{needsLoading ? 'Looking at the journey…' : 'Nothing to have ready.'}</p>
        {/each}
      </div>

      {#if startError}
        <p class="mvi2-error">{startError}</p>
      {/if}
      <div class="mvi2-spacer"></div>
    </div>

    <div class="mvi2-actions">
      <button type="button" class="mvi2-btn" disabled={starting} onclick={startCall}>
        {starting ? 'Starting…' : 'Start the call'}
        <Icon name="arrow" color="#12E2F7" />
      </button>
    </div>
  {/if}

  {#snippet overlay()}
    {#if panelOpen}
      <FactsPanel workflowId={selectedId} bind:notes onclose={() => (panelOpen = false)} />
    {/if}
  {/snippet}
</Phone>
