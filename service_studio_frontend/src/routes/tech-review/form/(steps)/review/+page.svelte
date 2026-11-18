<script lang="ts">
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { techReviewSteps } from '$lib/form-editor/review-steps';
</script>

<svelte:head>
	<title>Review and send: Technical review | Service Studio</title>
</svelte:head>

<!-- The last step of the technical review. What it shows and sends comes in a later change. -->
<ReviewStep
	steps={techReviewSteps(['complete', 'complete', 'complete', 'current'])}
	heading="Review and send"
	hint="Check the technical review before it is sent for owner review."
>
	<p class="govuk-body">A summary of the technical review is shown here.</p>

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/tech-review/form/step-values')}>Back</a>
		<a class="govuk-button govuk-!-margin-bottom-0" href={resolve('/owner-review/form')}>Continue to owner review</a>
	{/snippet}
</ReviewStep>
