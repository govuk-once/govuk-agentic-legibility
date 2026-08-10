<script lang="ts">
  let { steps }: { steps: number[] } = $props()
</script>

<div class="flex">
  <div class="flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm text-gray-500">
    <span>added step{steps.length === 1 ? '' : 's'}</span>
    {#each steps as number (number)}
      <span
        class="inline-flex items-center justify-center rounded-full bg-blue-600 text-white text-xs"
        style="width: 20px; height: 20px;"
      >
        {number}
      </span>
    {/each}
  </div>
</div>
