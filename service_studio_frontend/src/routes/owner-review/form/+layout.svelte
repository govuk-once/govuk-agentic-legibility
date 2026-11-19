<script lang="ts">
	import ReviewLayout from '$lib/components/ReviewLayout.svelte';
	import type { LayoutProps } from './$types';

	// Every page of the owner review, and the page after publishing, has the same header.
	let { children }: LayoutProps = $props();
</script>

<ReviewLayout>{@render children()}</ReviewLayout>
