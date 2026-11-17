<script lang="ts">
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { stagesAt } from '$lib/components/progress-stages';
	import { ownerReviewProgress } from '$lib/form-editor/owner-review-progress.svelte';
	import type { LayoutProps } from './$types';

	// The header, the stages and the title are the same on every step of the owner review, so they are drawn once here.
	let { data, children }: LayoutProps = $props();

	// The example problems stand for a tech review that is not finished, so the banner says so while they are shown.
	const stages = $derived(stagesAt('Owner review', ownerReviewProgress.showExampleProblems ? ['Tech review'] : []));
</script>

<ServiceHeader />
<Progress {stages} />

<main>
	<div class="owner-review__title govuk-!-padding-top-6">
		<span class="govuk-caption-m govuk-!-margin-bottom-2">{data.workflow.manifest.description}</span>
		<h1 class="govuk-heading-xl govuk-!-margin-bottom-2">Owner review</h1>
		<p class="govuk-body govuk-!-margin-bottom-0">Check the details, clear any problems, then sign off so the form can be published.</p>
	</div>
	{@render children()}
</main>

<style>
	/* Lines the title up with GOV.UK in the header. */
	.owner-review__title {
		padding-inline: 40px;
	}

	@media (max-width: 640px) {
		.owner-review__title {
			padding-inline: 15px;
		}
	}
</style>
