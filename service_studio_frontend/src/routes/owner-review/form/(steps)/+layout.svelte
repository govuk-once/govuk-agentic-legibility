<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ReviewPageTitle from '$lib/components/ReviewPageTitle.svelte';
	import { stagesAt } from '$lib/components/progress-stages';
	import { isTechReviewFinished } from '$lib/form-editor/tech-review-summary';
	import type { LayoutProps } from './$types';

	// The stages and the title are the same on every step of the owner review, so they are drawn once here. The page
	// after publishing sits outside this group, because it has neither.
	let { data, children }: LayoutProps = $props();

	// The owner comes to these pages twice: first to add their details before the technical review, then to sign off
	// once it is finished. The banner shows which of the two visits this is.
	const stages = $derived(stagesAt(isTechReviewFinished(data.workflow) ? 'Sign off' : 'Owner review'));
</script>

<Progress {stages} />

<main>
	<!-- The owner can go back to the editor at any point, to change the form and send it on again. The editor opens
		the same draft, because it is the one open in this browser tab. -->
	<div class="owner-review__back">
		<a class="govuk-back-link" href={resolve('/edit-form/draft')}>Back to the editor</a>
	</div>
	<ReviewPageTitle
		caption={data.workflow.manifest.description}
		heading="Owner review"
		intro="Check the details, clear any problems, then sign off so the form can be published."
	/>
	{@render children()}
</main>

<style>
	.owner-review__back {
		padding-inline: 40px;
	}

	@media (max-width: 640px) {
		.owner-review__back {
			padding-inline: 15px;
		}
	}
</style>
