<script lang="ts">
	import { resolve } from '$app/paths';
	import DraftProblemPage from '$lib/components/DraftProblemPage.svelte';
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { stagesAt } from '$lib/components/progress-stages';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>Owner review | Service Studio</title>
</svelte:head>

{#if data.form.ok}
	<ServiceHeader />
	<Progress stages={stagesAt('Owner review')} />

	<main class="govuk-!-padding-7">
		<span class="govuk-caption-m govuk-!-margin-bottom-2">{data.form.workflow.manifest.description}</span>
		<h1 class="govuk-heading-xl">Owner review</h1>
		<p class="govuk-body">Check the details, clear any problems, then sign off so the form can be published.</p>
	</main>
{:else}
	<DraftProblemPage problem={data.form} startRoute="/edit-form">
		{#snippet missing()}
			<h1 class="govuk-heading-xl">Nothing to review yet</h1>
			<p class="govuk-body">
				There is no form in this browser tab. <a class="govuk-link" href={resolve('/edit-form')}>Open a form</a>, edit it and
				send it to tech review to review it here.
			</p>
		{/snippet}
	</DraftProblemPage>
{/if}
