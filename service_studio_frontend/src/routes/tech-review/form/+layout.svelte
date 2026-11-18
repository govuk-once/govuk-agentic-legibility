<script lang="ts">
	import ReviewLayout from '$lib/components/ReviewLayout.svelte';
	import type { LayoutProps } from './$types';

	// Every page of the technical review has the same header. A page that is not one of the numbered steps, such as
	// finding an endpoint, sits outside the steps group and draws its own title.
	let { children }: LayoutProps = $props();
</script>

<ReviewLayout>{@render children()}</ReviewLayout>
