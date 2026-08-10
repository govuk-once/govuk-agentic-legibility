<script lang="ts">
  import type { StateSummary } from '../types'

  const {
    allStates,
    currentStateName,
    onSelect,
  }: {
    allStates: StateSummary[]
    currentStateName: string
    onSelect: (name: string) => void
  } = $props()

  // Description of the currently selected state, shown at the foot of the panel
  // so the state badge no longer needs to live in the top bar.
  const currentDescription = $derived(
    allStates.find((s) => s.name === currentStateName)?.description ?? ''
  )
</script>

<nav class="flex flex-col h-full p-4">
  <div class="space-y-3">
    {#each allStates as s (s.name)}
      {@const active = s.name === currentStateName}
      <button
        onclick={() => onSelect(s.name)}
        class="w-full text-left px-3 py-2.5 rounded-lg text-base flex items-center gap-3 transition-colors
          {active
            ? 'bg-blue-50 text-black font-bold'
            : 'bg-white text-black font-normal hover:bg-gray-50'}"
        title={s.description}
      >
        <span
          class="w-2.5 h-2.5 rounded-full flex-shrink-0 {active ? 'bg-blue-600' : 'bg-[#D2D5D7]'}"
        ></span>
        {s.name}
      </button>
    {/each}
  </div>

  {#if currentDescription}
    <p class="mt-auto px-2 pt-4 text-base text-gray-500">
      {currentDescription}
    </p>
  {/if}
</nav>
