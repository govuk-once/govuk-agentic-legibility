<script lang="ts">
  import type { ToolGroup } from './toolGroups'

  let { group }: { group: ToolGroup } = $props()

  let open = $state(false)

  // How many calls in this group advanced a journey step. Shown in the summary.
  const becameSteps = $derived(group.rows.filter((r) => r.addedStep !== null).length)
</script>

<div class="flex justify-center">
  <details class="max-w-[90%] w-full text-sm" bind:open>
    <summary
      class="flex items-center justify-between gap-2 px-3 py-2 rounded-[10px] border border-gray-200 bg-white cursor-pointer select-none list-none"
    >
      <span class="flex items-center gap-2">
        <span class="inline-block transition-transform {open ? 'rotate-90' : ''}">&rsaquo;</span>
        <span class="font-semibold text-gray-700">
          {group.rows.length} tool call{group.rows.length === 1 ? '' : 's'}
        </span>
        <span class="text-gray-500">
          {becameSteps} became journey step{becameSteps === 1 ? '' : 's'}
        </span>
      </span>
      <span class="text-blue-600">{open ? 'Hide' : 'Show'}</span>
    </summary>

    {#if open}
      <div class="mt-1 rounded-[10px] border border-gray-200 divide-y divide-gray-200">
        {#each group.rows as row (row.message.id)}
          <details>
            <summary
              class="flex items-center justify-between gap-2 px-3 py-2 cursor-pointer select-none list-none"
            >
              <span class="flex items-center gap-2 min-w-0">
                <span class="text-gray-400">&rsaquo;</span>
                <span class="font-mono text-gray-700 truncate">{row.message.toolName}</span>
              </span>
              {#if row.addedStep !== null}
                <span class="flex flex-shrink-0 items-center gap-1 text-gray-500">
                  added step
                  <span
                    class="inline-flex items-center justify-center rounded-full bg-blue-600 text-white text-xs"
                    style="width: 20px; height: 20px;"
                  >
                    {row.addedStep}
                  </span>
                </span>
              {:else}
                <span class="flex-shrink-0 text-gray-400">no step added</span>
              {/if}
            </summary>

            <div class="px-3 pb-3 pt-1 font-mono text-sm space-y-2">
              {#if row.message.toolArgs && Object.keys(row.message.toolArgs as object).length > 0}
                <div>
                  <p class="text-gray-500 mb-1">Arguments</p>
                  <pre class="bg-white border border-gray-200 rounded p-2 overflow-x-auto text-gray-700">{JSON.stringify(row.message.toolArgs, null, 2)}</pre>
                </div>
              {/if}
              <div>
                <p class="text-gray-500 mb-1">Result</p>
                <pre class="bg-white border border-gray-200 rounded p-2 overflow-x-auto text-gray-700 whitespace-pre-wrap">{row.message.toolResult}</pre>
              </div>
            </div>
          </details>
        {/each}
      </div>
    {/if}
  </details>
</div>
