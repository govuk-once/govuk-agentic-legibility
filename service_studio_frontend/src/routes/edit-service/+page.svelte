<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { editStages } from '$lib/components/progress-stages';
	import { serviceExamples } from '$lib/examples/services';
	import { tidyCode } from '$lib/graph-kit/tidy-code';

	// The slug of the example chosen in the list. It starts on the first example so the page never
	// opens with nothing chosen.
	let selectedSlug = $state(serviceExamples[0]?.slug ?? '');
	const selectedExample = $derived(serviceExamples.find((example) => example.slug === selectedSlug) ?? null);

	// The number of states in every process of the chosen workflow, shown so the size of a service is
	// clear before it is opened.
	const stateCount = $derived(
		Object.values(selectedExample?.workflow?.processes ?? {}).reduce(
			(total, process) => total + Object.keys(process.states).length,
			0
		)
	);
	const processCount = $derived(Object.keys(selectedExample?.workflow?.processes ?? {}).length);
</script>

<svelte:head>
	<title>Edit and review the journey (unified schema) | Service Studio</title>
</svelte:head>

<ServiceHeader />

<main class="picker-page">
	<Progress stages={editStages} />

	<div class="picker-page__content govuk-!-padding-7">
		<h1 class="govuk-heading-xl">Edit and review the journey</h1>
		<p class="govuk-body">
			This page works on the unified schema. Choose a service below to see whether it matches the schema,
			then open the graph.
		</p>

		<div class="govuk-form-group picker-page__select">
			<label class="govuk-label govuk-label--s" for="example-workflow">Choose a service</label>
			<select class="govuk-select" id="example-workflow" bind:value={selectedSlug}>
				{#each serviceExamples as example (example.slug)}
					<option value={example.slug}>{tidyCode(example.slug)}</option>
				{/each}
			</select>
		</div>

		{#if selectedExample && !selectedExample.workflow}
			<div class="govuk-error-summary" role="alert">
				<h2 class="govuk-error-summary__title">This service does not match the schema</h2>
				<div class="govuk-error-summary__body">
					<ul class="govuk-list govuk-error-summary__list">
						{#each selectedExample.issues as issue, index (index)}
							<li>{issue.path}: {issue.message}</li>
						{/each}
					</ul>
				</div>
			</div>
		{:else if selectedExample?.workflow}
			<dl class="picker-page__stats">
				<div class="picker-page__stat">
					<dt class="govuk-heading-l govuk-!-margin-bottom-0">{processCount}</dt>
					<dd class="govuk-body govuk-!-margin-bottom-0">{processCount === 1 ? 'process' : 'processes'}</dd>
				</div>
				<div class="picker-page__stat">
					<dt class="govuk-heading-l govuk-!-margin-bottom-0">{stateCount}</dt>
					<dd class="govuk-body govuk-!-margin-bottom-0">{stateCount === 1 ? 'state' : 'states'}</dd>
				</div>
			</dl>

			{#if selectedExample.warnings.length > 0}
				<div class="govuk-warning-text">
					<span class="govuk-warning-text__icon" aria-hidden="true">!</span>
					<strong class="govuk-warning-text__text">
						<span class="govuk-visually-hidden">Warning</span>
						This service matches the schema, with {selectedExample.warnings.length === 1
							? '1 warning'
							: `${selectedExample.warnings.length} warnings`}
					</strong>
				</div>
				<ul class="govuk-list govuk-list--bullet">
					{#each selectedExample.warnings as warning, index (index)}
						<li>{warning.path}: {warning.message}</li>
					{/each}
				</ul>
			{:else}
				<p class="govuk-body">This service matches the schema with no warnings.</p>
			{/if}

			<a
				class="govuk-button picker-page__open picker-page__open--blue"
				href={resolve('/edit-service/[slug]', { slug: selectedExample.slug })}
			>
				Open the graph
				<svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
					<rect x="1" y="1" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" />
					<path d="M5 5 H13 V13" fill="none" stroke="currentColor" stroke-width="1.6" />
				</svg>
			</a>
		{/if}
	</div>
</main>

<style>
	.picker-page {
		flex-grow: 1;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.picker-page__content {
		max-width: 700px;
	}

	.picker-page__select {
		max-width: 420px;
		margin-top: 20px;
		margin-bottom: 30px;
	}

	.picker-page__stats {
		display: flex;
		width: fit-content;
		margin: 0 0 30px;
		border: 1px solid #b1b4b6;
	}

	.picker-page__stat {
		display: flex;
		flex-direction: column;
		gap: 5px;
		padding: 15px 20px;
		background-color: #f3f2f1;
	}

	.picker-page__stat + .picker-page__stat {
		border-left: 1px solid #b1b4b6;
	}

	.picker-page__stat dt {
		margin: 0;
	}

	.picker-page__stat dd {
		margin: 0;
		color: #505a5f;
	}

	.picker-page__open {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 0;
	}

	/* The GOV.UK Design System has no blue button variant of its own, blue is normally reserved for
		links, but this screen's own design calls for a blue primary action here. */
	.picker-page__open--blue {
		background-color: #1d70b8;
		box-shadow: 0 2px 0 #003078;
	}

	.picker-page__open--blue:hover {
		background-color: #003078;
	}
</style>
