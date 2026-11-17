<script lang="ts">
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import type { LayoutProps } from './$types';

	// Every page of the owner review, and the page after publishing, has the same header.
	let { children }: LayoutProps = $props();
</script>

<ServiceHeader />
{@render children()}
