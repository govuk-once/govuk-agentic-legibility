<script lang="ts">
  import ServiceHeader from '$lib/components/ServiceHeader.svelte';
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();
</script>

<ServiceHeader />

<main class="govuk-width-container">
  {@render children()}
</main>
