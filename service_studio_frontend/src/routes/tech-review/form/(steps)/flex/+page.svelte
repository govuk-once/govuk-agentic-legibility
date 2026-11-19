<script lang="ts">
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { techReviewSteps } from '$lib/form-editor/review-steps';
</script>

<svelte:head>
	<title>Flex connections: Technical review | Service Studio</title>
</svelte:head>

<!-- The second step of the technical review. Its list of API calls comes in a later change. -->
<ReviewStep
	steps={techReviewSteps(['complete', 'current', 'upcoming', 'upcoming'])}
	heading="Flex connections"
	hint="Connect each API call to a Flex endpoint."
>
	<p class="govuk-body">The API calls are listed here.</p>

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/tech-review/form')}>Back</a>
		<a class="govuk-button govuk-!-margin-bottom-0" href={resolve('/owner-review/form')}>Continue to owner review</a>
	{/snippet}
</ReviewStep>
