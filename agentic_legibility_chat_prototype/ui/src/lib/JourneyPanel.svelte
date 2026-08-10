<script lang="ts">
  import type { JourneyStep } from './journey'

  let {
    steps,
    onClose,
  }: {
    steps: JourneyStep[]
    onClose: () => void
  } = $props()

  // Placeholder field-level provenance. Real values need a backend signal that
  // records where each answer came from, so this block exists only to preview
  // the tag design and is clearly labelled as a sample in the panel. The colours
  // are the govuk-tag values from the design spec.
  const sampleFields = [
    { label: 'Name, licence no.', tag: 'on file', variant: 'blue' },
    { label: 'New address', tag: 'you told me', variant: 'green' },
    { label: 'New photocard', tag: 'I resolved', variant: 'yellow' },
    { label: 'Move-in date', tag: 'awaiting answer', variant: 'red' },
  ]

  const tagStyles: Record<string, string> = {
    blue: 'text-[#0f385c] bg-[#d2e2f1]',
    green: 'text-[#083d29] bg-[#cfe4dc]',
    yellow: 'text-[#7a3c1c] bg-[#ffee80]',
    red: 'text-[#651b1b] bg-[#f4d7d7]',
  }
</script>

<div class="flex flex-col h-full">
  <header class="flex items-center justify-between px-4 py-3 border-b border-gray-200">
    <div class="flex items-baseline gap-2">
      <span class="text-base font-bold text-black">Agent Journey</span>
      <span class="text-sm text-gray-500">
        {steps.length} step{steps.length === 1 ? '' : 's'} so far
      </span>
    </div>
    <button onclick={onClose} class="text-base text-blue-600 hover:underline">Hide</button>
  </header>

  <div class="flex-1 overflow-y-auto p-4">
    {#if steps.length === 0}
      <p class="text-base text-gray-500">
        No service plan yet. Ask about a government service and its steps will appear here.
      </p>
    {:else}
      <ol class="space-y-4">
        {#each steps as step (step.number)}
          <li class="flex gap-3">
            <span
              class="flex-shrink-0 flex items-center justify-center rounded-full bg-blue-600 text-white text-sm font-semibold"
              class:opacity-40={step.status === 'awaiting'}
              style="width: 22px; height: 22px;"
            >
              {step.number}
            </span>
            <div class="min-w-0">
              <p class="text-base font-bold text-black">{step.title}</p>
              <p class="text-sm text-gray-500">
                {step.required ? 'Required' : 'Optional'}
                {#if step.status === 'done'}· done{:else if step.status === 'active'}· in progress{/if}
              </p>
              {#if step.result}
                <p class="mt-1 text-sm text-gray-600 font-mono break-words">{step.result}</p>
              {/if}
              {#if step.note}
                <p class="mt-1 text-sm text-gray-500">{step.note}</p>
              {/if}
            </div>
          </li>
        {/each}
      </ol>

      <!-- Design preview of the per-field provenance tags, not live data. -->
      <div class="mt-6 rounded-[14px] border border-gray-200 p-3">
        <p class="mb-2 text-sm text-gray-500">Sample field detail (design preview, not live data)</p>
        <div class="space-y-2">
          {#each sampleFields as field (field.label)}
            <div class="flex items-center justify-between gap-2">
              <span class="text-base text-black">{field.label}</span>
              <span class="rounded-md px-2 py-0.5 text-sm font-medium {tagStyles[field.variant]}">
                {field.tag}
              </span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>
