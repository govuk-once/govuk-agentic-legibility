<script lang="ts">
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { ownerReviewSteps } from '$lib/form-editor/owner-review-steps';
</script>

<svelte:head>
	<title>Sign off: Owner review | Service Studio</title>
</svelte:head>

<!-- The last step of the owner review. Its checklist and the Publish button come in a later change. -->
<ReviewStep
	steps={ownerReviewSteps(['complete', 'complete', 'current'])}
	heading="Sign off"
	hint="Confirm everything is in place. Publishing makes this form live and tells the department that you accept it."
>
	<p class="govuk-body">The checklist is shown here.</p>

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/owner-review/form/review')}>Back</a>
	{/snippet}
</ReviewStep>
