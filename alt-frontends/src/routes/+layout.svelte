<script lang="ts">
  import ServiceHeader from '$lib/components/ServiceHeader.svelte';
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();
</script>

<ServiceHeader />

<!-- Spacing unit 7 keeps the page content clear of the header's bottom border. -->
<main class="govuk-width-container govuk-!-margin-top-7">
  {@render children()}
</main>
