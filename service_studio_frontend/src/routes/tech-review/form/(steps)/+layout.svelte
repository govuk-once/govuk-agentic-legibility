<script lang="ts">
	import Progress from '$lib/components/Progress.svelte';
	import ReviewPageTitle from '$lib/components/ReviewPageTitle.svelte';
	import { techReviewStages } from '$lib/components/progress-stages';
	import type { LayoutProps } from './$types';

	// The stages and the title are the same on every step of the technical review, so they are drawn once here.
	let { data, children }: LayoutProps = $props();
</script>

<Progress stages={techReviewStages} />

<main>
	<ReviewPageTitle
		caption={data.workflow.manifest.description}
		heading="Technical review"
		intro="Set up the technical side of this form: workflow settings, Flex connections, then each developer step."
	/>
	{@render children()}
</main>
