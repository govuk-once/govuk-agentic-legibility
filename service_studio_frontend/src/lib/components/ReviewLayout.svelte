<script lang="ts">
	import type { Snippet } from 'svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';

	/*
		The frame around every page of a review: the header, then the page. The frame fills at least the height of the
		window and lets the page's main area grow into any space left over, so the bar of buttons at the bottom of a
		review step sits at the bottom of the window on a short page instead of halfway up it.
	*/
	let { children }: { children: Snippet } = $props();
</script>

<div class="review-layout">
	<ServiceHeader />
	{@render children()}
</div>

<style>
	.review-layout {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
	}

	/* The main area of each page takes the space left over, and is a column so the bar of buttons can be pushed down. */
	.review-layout > :global(main) {
		display: flex;
		flex: 1 0 auto;
		flex-direction: column;
	}
</style>
