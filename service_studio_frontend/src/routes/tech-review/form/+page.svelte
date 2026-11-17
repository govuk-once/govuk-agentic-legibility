<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { techReviewStages } from '$lib/components/progress-stages';
</script>

<svelte:head>
	<title>Tech review | Service Studio</title>
</svelte:head>

<!-- A placeholder until the tech review is designed, so a form that passes its checks has somewhere to go. The edited
	form waits in the browser tab, and the owner review opens it from there. -->
<ServiceHeader />
<Progress stages={techReviewStages} />

<main class="govuk-!-padding-7">
	<h1 class="govuk-heading-xl">Tech review</h1>
	<p class="govuk-body">Review the tech elements of the schema.</p>
	<a class="govuk-button" href={resolve('/owner-review/form')}>Continue to owner review</a>
</main>
