<script lang="ts">
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { techReviewStages } from '$lib/components/progress-stages';
</script>

<svelte:head>
	<title>Tech review | Service Studio</title>
</svelte:head>

<!-- A placeholder until the tech review is designed, so a form that passes its checks has somewhere to go. The form
	that was edited is not carried here yet. -->
<ServiceHeader />
<Progress stages={techReviewStages} />

<main class="govuk-!-padding-7">
	<h1 class="govuk-heading-xl">Tech review</h1>
	<p class="govuk-body">Review the tech elements of the schema.</p>
</main>
