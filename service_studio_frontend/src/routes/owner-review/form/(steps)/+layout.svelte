<script lang="ts">
	import Progress from '$lib/components/Progress.svelte';
	import ReviewPageTitle from '$lib/components/ReviewPageTitle.svelte';
	import { stagesAt } from '$lib/components/progress-stages';
	import { formStageLinks } from '$lib/form-editor/form-stage-links';
	import { isTechReviewFinished } from '$lib/form-editor/tech-review-summary';
	import type { LayoutProps } from './$types';

	// The stages and the title are the same on every step of the owner review, so they are drawn once here. The page
	// after publishing sits outside this group, because it has neither.
	let { data, children }: LayoutProps = $props();

	// The owner comes to these pages twice: first to add their details before the technical review, then to sign off
	// once it is finished. The banner shows which of the two visits this is, and links back to the stages before it.
	const stages = $derived(stagesAt(isTechReviewFinished(data.workflow) ? 'Sign off' : 'Owner review', formStageLinks));
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

