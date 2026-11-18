<script lang="ts">
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { techReviewSteps } from '$lib/form-editor/review-steps';
</script>

<svelte:head>
	<title>Step values: Technical review | Service Studio</title>
</svelte:head>

<!-- The third step of the technical review. Its list of developer steps comes in a later change. -->
<ReviewStep
	steps={techReviewSteps(['complete', 'complete', 'current', 'upcoming'])}
	heading="Step values"
	hint="Check the values of each developer step."
>
	<p class="govuk-body">The developer steps are listed here.</p>

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/tech-review/form/flex')}>Back</a>
		<a class="govuk-button govuk-!-margin-bottom-0" href={resolve('/owner-review/form')}>Continue to owner review</a>
	{/snippet}
</ReviewStep>
