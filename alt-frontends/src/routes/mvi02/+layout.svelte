<script lang="ts">
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();
</script>

<!-- The /mvi02 look lives in its own stylesheet, so it is loaded only on these pages. -->
<svelte:head>
  <link rel="stylesheet" href="/mvi02.css" />
</svelte:head>

{@render children()}
