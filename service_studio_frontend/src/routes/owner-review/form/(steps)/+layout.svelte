<script lang="ts">
	import Progress from '$lib/components/Progress.svelte';
	import ReviewPageTitle from '$lib/components/ReviewPageTitle.svelte';
	import { stagesAt } from '$lib/components/progress-stages';
	import { ownerReviewProgress } from '$lib/form-editor/owner-review-progress.svelte';
	import type { LayoutProps } from './$types';

	// The stages and the title are the same on every step of the owner review, so they are drawn once here. The page
	// after publishing sits outside this group, because it has neither.
	let { data, children }: LayoutProps = $props();

	// The example problems stand for a tech review that is not finished, so the banner says so while they are shown.
	const stages = $derived(stagesAt('Owner review', ownerReviewProgress.showExampleProblems ? ['Tech review'] : []));
</script>

<Progress {stages} />

<main>
	<ReviewPageTitle
		caption={data.workflow.manifest.description}
		heading="Owner review"
		intro="Check the details, clear any problems, then sign off so the form can be published."
	/>
	{@render children()}
</main>
