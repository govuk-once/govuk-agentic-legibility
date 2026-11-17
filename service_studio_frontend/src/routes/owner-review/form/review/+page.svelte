<script lang="ts">
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { ownerReviewSteps } from '$lib/form-editor/owner-review-steps';
</script>

<svelte:head>
	<title>Review: Owner review | Service Studio</title>
</svelte:head>

<!-- The second step of the owner review. Its checks and the list of steps in the journey come in a later change. -->
<ReviewStep
	steps={ownerReviewSteps(['complete', 'current', 'upcoming'])}
	heading="Review"
	hint="Check the technical review, clear any validation problems and look through the journey."
>
	<p class="govuk-body">The checks and the journey are shown here.</p>

	{#snippet actions()}
		<a class="govuk-link govuk-body-l govuk-!-margin-bottom-0" href={resolve('/owner-review/form')}>Back</a>
	{/snippet}
</ReviewStep>
