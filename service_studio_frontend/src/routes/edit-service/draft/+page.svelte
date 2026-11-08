<script lang="ts">
	import { resolve } from '$app/paths';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import ServiceEditorPage from '$lib/service-editor/components/ServiceEditorPage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<!-- The editing page sets its own title, so this one is only for the page that says why there is nothing to edit. -->
<svelte:head>
	{#if !data.draft.ok}
		<title>Open the draft | Service Studio</title>
	{/if}
</svelte:head>

{#if data.draft.ok}
	<!-- The draft names its entry process after the service, so that code names the service on the page. -->
	<ServiceEditorPage slug={data.draft.workflow.manifest.entry} workflow={data.draft.workflow} />
{:else}
	<ServiceHeader />

	<main class="govuk-!-padding-top-9 govuk-!-padding-bottom-9 draft-problem">
		{#if data.draft.reason === 'missing'}
			<h1 class="govuk-heading-xl">Nothing to edit yet</h1>
			<p class="govuk-body">
				There is no draft in this browser tab. <a class="govuk-link" href={resolve('/onboard/service/method')}>Generate a first draft</a>
				and choose Edit to open it here.
			</p>
		{:else}
			<h1 class="govuk-heading-xl">The draft could not be opened</h1>
			<div class="govuk-error-summary" role="alert">
				<h2 class="govuk-error-summary__title">This did not match the required format</h2>
				<div class="govuk-error-summary__body">
					<ul class="govuk-list govuk-error-summary__list">
						{#each data.draft.issues as issue, index (index)}
							<li>{issue.path}: {issue.message}</li>
						{/each}
					</ul>
				</div>
			</div>
			<p class="govuk-body">
				<a class="govuk-link" href={resolve('/onboard/service/method')}>Generate a new draft</a>.
			</p>
		{/if}
	</main>
{/if}

<style>
	/* The left edge matches the Service Studio name, as on the onboarding pages. */
	.draft-problem {
		max-width: 700px;
		margin-left: 145px;
	}

	@media (max-width: 40.0525em) {
		.draft-problem {
			padding-right: 15px;
			padding-left: 15px;
			margin-left: 0;
		}
	}
</style>
