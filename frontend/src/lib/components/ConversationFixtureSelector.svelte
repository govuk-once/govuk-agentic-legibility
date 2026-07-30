<script lang="ts">
  import type { ConversationFixture } from '$lib/types';

  export let fixtures: ConversationFixture[] = [];
  export let selectedId: string | null = null;
  export let loading = false;
  export let error = '';
  export let onSelect: (fixtureId: string | null) => void;

  $: selected = fixtures.find((fixture) => fixture.id === selectedId) ?? null;

  function change(event: Event): void {
    const value = (event.currentTarget as HTMLSelectElement).value;
    onSelect(value || null);
  }
</script>

<section class="fixture" aria-labelledby="fixture-heading">
  <span class="eyebrow">Evaluation input</span>
  <h3 id="fixture-heading">Conversation scenario</h3>
  <p>
    Select a version-controlled conversation to demonstrate how earlier context can
    populate each service interaction. The same fixtures can be used by automated runs.
  </p>

  {#if error}
    <div class="error" role="alert">{error}</div>
  {:else}
    <label for="fixture-select">Conversation history</label>
    <select
      id="fixture-select"
      value={selectedId ?? ''}
      onchange={change}
      disabled={loading}
    >
      <option value="">No fixture — complete the form manually</option>
      {#each fixtures as fixture}
        <option value={fixture.id}>{fixture.title}</option>
      {/each}
    </select>
  {/if}

  {#if selected}
    <div class="preview">
      <strong>{selected.title}</strong>
      <span>{selected.description}</span>
      <ol>
        {#each selected.conversation as message}
          <li class:user={message.role === 'user'}>
            <span>{message.role}</span>
            <p>{message.content}</p>
          </li>
        {/each}
      </ol>
    </div>
  {/if}
</section>

<style>
  .fixture { margin: 1.5rem 0 1.75rem; border: 1px solid #b1b4b6; background: #f3f2f1; padding: 1rem 1.1rem 1.15rem; }
  .eyebrow { color: #1d70b8; font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h3 { margin: .15rem 0 .45rem; font-size: 1.2rem; }
  .fixture > p { margin: 0 0 1rem; color: #505a5f; }
  label { display: block; margin-bottom: .4rem; font-weight: 700; }
  select { width: min(100%,36rem); min-height: 2.75rem; border: 2px solid #0b0c0c; background: #fff; padding: .4rem .55rem; font: inherit; }
  select:focus { outline: .2rem solid #ffdd00; outline-offset: 0; box-shadow: inset 0 0 0 2px #0b0c0c; }
  .preview { display: grid; gap: .2rem; margin-top: 1rem; border-left: .3rem solid #1d70b8; background: #fff; padding: .85rem 1rem; }
  .preview > span { color: #505a5f; font-size: .9rem; }
  ol { display: grid; gap: .55rem; margin: .75rem 0 0; padding: 0; list-style: none; }
  li { border-left: .25rem solid #b1b4b6; padding-left: .7rem; }
  li.user { border-color: #1d70b8; }
  li span { color: #505a5f; font-size: .68rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  li p { margin: .1rem 0 0; }
  .error { border-left: .3rem solid #d4351c; background: #fff; padding: .75rem .9rem; }
</style>
