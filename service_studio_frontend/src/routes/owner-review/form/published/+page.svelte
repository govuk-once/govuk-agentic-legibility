<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import Progress from '$lib/components/Progress.svelte';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { publishedStages } from '$lib/components/progress-stages';

	// What Publish passed on about the form. Its draft has been deleted, so this is the only place it is held. It is
	// not there when the page is reloaded or opened directly, because it comes with the navigation from Publish.
	const published = $derived(page.state.published);

	// When the form was published. Publishing does not send it anywhere yet, so this is when the page was opened, which
	// is straight after Publish was chosen.
	const publishedAt = new Date();
	const publishedDate = publishedAt.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
	const publishedTime = publishedAt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

	// What has happened now the form is published. These describe how publishing will work once it sends the form to
	// the workflow server, so for now they are what the design says.
	const nextSteps = $derived([
		{
			key: 'The form is live',
			value: 'People can start using it now. Anyone already part way through finishes on the version before.'
		},
		{ key: 'You have been emailed', value: `A copy of this sign off went to ${published?.contact}.` },
		{ key: 'The team has been told', value: 'The department team can see it is published.' },
		{
			key: 'Changing it later',
			value: 'Any change creates a new version. It goes back through technical review and owner review before it is published.'
		}
	]);
</script>

<svelte:head>
	<title>Form published | Service Studio</title>
</svelte:head>

<Progress stages={publishedStages} />

<main>
	{#if !published}
		<div class="published__banner">
			<h1 class="govuk-heading-xl">Form published</h1>
			<p class="govuk-body">
				This page shows a form straight after it is published. <a class="govuk-link" href={resolve('/onboard')}>Go to the start page</a>
				to start a new form or open one of your drafts.
			</p>
		</div>
	{:else}
		<div class="published__banner">
			<div class="govuk-panel govuk-panel--confirmation govuk-!-margin-bottom-0">
				<h1 class="govuk-panel__title">Form published</h1>
				<div class="govuk-panel__body govuk-!-font-size-19">
					{published.description} is now live. Version {published.version}, published {publishedDate} at {publishedTime}.
				</div>
			</div>
		</div>

		<ReviewStep heading="What happens next" hint="Nothing more is needed from you. We have told the people involved.">
			<dl class="govuk-summary-list published__list">
				{#each nextSteps as step (step.key)}
					<div class="govuk-summary-list__row">
						<dt class="govuk-summary-list__key">{step.key}</dt>
						<dd class="govuk-summary-list__value">{step.value}</dd>
					</div>
				{/each}
			</dl>

			{#snippet actions()}
				<button class="govuk-button govuk-!-margin-bottom-0" type="button" disabled>Go to service dashboard</button>
				<a class="govuk-link" role="link" aria-disabled="true">View the published journey</a>
			{/snippet}
		</ReviewStep>
	{/if}
</main>

<style>
	/* The panel sits inside the page margins, lined up with GOV.UK in the header, with its words on the left as the
		rest of the page is. */
	.published__banner {
		padding: 30px 40px 0;
	}

	.published__banner .govuk-panel {
		text-align: left;
	}

	/* A rule above the list, as above the other lists in the review. */
	.published__list {
		border-top: 2px solid #0b0c0c;
	}

	@media (max-width: 640px) {
		.published__banner {
			padding: 20px 15px 0;
		}
	}
</style>
