<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<!-- The shared layout supplies document metadata once so route components only manage page content. -->
<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<!-- Child content is rendered without another wrapper so route layout styles remain in control. -->
{@render children()}
