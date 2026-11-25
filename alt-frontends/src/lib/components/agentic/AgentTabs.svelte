<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    tabs: { id: string; label: string }[];
    /** The id of the tab that is showing. */
    selected: string;
    /** Something at the right-hand end of the tab bar, for example a switch that belongs to one tab. */
    aside?: Snippet;
    /** The content of the tab that is showing. It is given that tab's id. */
    children: Snippet<[string]>;
  }

  let { tabs, selected = $bindable(), aside, children }: Props = $props();

  // The left and right arrow keys move between the tabs, as people expect from a row of tabs.
  function onkeydown(event: KeyboardEvent) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    const index = tabs.findIndex((tab) => tab.id === selected);
    const step = event.key === 'ArrowRight' ? 1 : -1;
    const next = tabs[(index + step + tabs.length) % tabs.length];
    selected = next.id;
    document.getElementById(`agent-tab-${next.id}`)?.focus();
  }
</script>

<div class="agent-tabs">
  <div class="agent-tabs__bar">
    <div class="agent-tabs__list" role="tablist" tabindex="-1" {onkeydown}>
      {#each tabs as tab (tab.id)}
        <button
          type="button"
          role="tab"
          id="agent-tab-{tab.id}"
          class="agent-tabs__tab"
          class:agent-tabs__tab--selected={tab.id === selected}
          aria-selected={tab.id === selected}
          aria-controls="agent-tabpanel"
          tabindex={tab.id === selected ? 0 : -1}
          onclick={() => (selected = tab.id)}
        >
          {tab.label}
        </button>
      {/each}
    </div>
    {#if aside}
      {@render aside()}
    {/if}
  </div>

  <div class="agent-tabs__panel" role="tabpanel" id="agent-tabpanel" aria-labelledby="agent-tab-{selected}">
    {@render children(selected)}
  </div>
</div>

<style>
  /* A white frame with a thin grey outline and rounded corners. The tab bar sits across the top,
     split from the content by a line. */
  .agent-tabs {
    overflow: hidden;
    border: 1px solid #b1b4b6;
    border-radius: 14px;
    background-color: #ffffff;
  }

  .agent-tabs__bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 8px 16px;
    padding: 12px 20px;
    border-bottom: 1px solid #b1b4b6;
  }

  .agent-tabs__list {
    display: flex;
    gap: 4px;
  }

  /* A tab is plain text. The one that is showing has a grey background and darker text. */
  .agent-tabs__tab {
    padding: 8px 16px;
    border: 0;
    border-radius: 8px;
    background: none;
    color: #505a5f;
    font-family: 'GDS Transport', arial, sans-serif;
    font-size: 1.1875rem;
    white-space: nowrap;
    cursor: pointer;
  }

  .agent-tabs__tab--selected {
    background-color: #f3f2f1;
    color: #0b0c0c;
    font-weight: 400;
  }

  .agent-tabs__tab:focus-visible {
    outline: 3px solid #ffdd00;
    outline-offset: 0;
  }
</style>
