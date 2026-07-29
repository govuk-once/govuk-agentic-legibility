<script lang="ts">
  import { flattenData } from '$lib/schema';

  export let data: unknown;
  $: entries = flattenData(data);
</script>

{#if entries.length > 0}
  <section class="summary" aria-labelledby="summary-title">
    <h3 id="summary-title">Information to review</h3>
    <dl>
      {#each entries as [label, value]}
        <div><dt>{label}</dt><dd>{value}</dd></div>
      {/each}
    </dl>
  </section>
{/if}

<style>
  .summary { margin: 1.5rem 0; border: 1px solid #b1b4b6; background: #f8f8f8; }
  h3 { margin: 0; padding: .8rem 1rem; background: #e7f2f8; border-bottom: 1px solid #b1b4b6; font-size: 1rem; }
  dl { margin: 0; }
  dl div { display: grid; grid-template-columns: minmax(9rem,.8fr) minmax(0,1.2fr); gap: 1rem; padding: .75rem 1rem; border-bottom: 1px solid #d8d8d8; }
  dl div:last-child { border-bottom: 0; }
  dt { font-weight: 700; }
  dd { margin: 0; overflow-wrap: anywhere; }
  @media (max-width: 36rem) { dl div { grid-template-columns: 1fr; gap: .2rem; } }
</style>
