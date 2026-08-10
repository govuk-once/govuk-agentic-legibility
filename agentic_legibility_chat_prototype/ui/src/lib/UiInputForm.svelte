<script lang="ts">
  import { invoke } from '@tauri-apps/api/core'
  import type { UiInputRequest } from '../types'

  const {
    request,
    onSubmit,
  }: {
    request: UiInputRequest
    onSubmit: () => void
  } = $props()

  let value = $state('')
  let submitting = $state(false)

  const isSelect = $derived(
    request.input_type === 'select' && (request.options?.length ?? 0) > 0
  )

  // Send the chosen value back to the host and clear the prompt. Guards against
  // empty values and against a second submit while the first is still in flight.
  async function submitValue(submitted: string) {
    if (!submitted || submitting) return
    submitting = true
    await invoke('submit_ui_input', { value: submitted })
    onSubmit()
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey && !isSelect) {
      e.preventDefault()
      submitValue(value.trim())
    }
  }
</script>

<div class="absolute inset-x-0 bottom-0 z-10 border-t border-gray-200 bg-white px-4 py-3 shadow-lg">
  <p class="mb-3 text-base font-bold text-black">{request.description}</p>

  {#if isSelect}
    <!-- Each option submits on its own click, so no separate confirm button. -->
    <div class="flex flex-wrap gap-3">
      {#each request.options ?? [] as opt (opt)}
        <button
          onclick={() => submitValue(opt)}
          disabled={submitting}
          class="rounded-2xl border-2 border-blue-600 bg-white px-4 py-2.5 text-base font-bold text-blue-600
                 hover:bg-blue-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {opt}
        </button>
      {/each}
    </div>
  {:else}
    <div class="flex items-end gap-2">
      <input
        type={request.input_type === 'number'
          ? 'number'
          : request.input_type === 'date'
            ? 'date'
            : request.input_type === 'email'
              ? 'email'
              : 'text'}
        bind:value
        onkeydown={onKeydown}
        placeholder={request.description}
        disabled={submitting}
        class="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-base
               focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
               disabled:bg-gray-50"
      />
      <button
        onclick={() => submitValue(value.trim())}
        disabled={submitting || !value.trim()}
        class="flex-shrink-0 rounded-xl bg-[#00703C] px-5 py-2 text-base font-bold text-white
               hover:bg-[#005a30] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? 'Sending…' : 'Submit'}
      </button>
    </div>
  {/if}
</div>
