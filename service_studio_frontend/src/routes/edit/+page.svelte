<script lang="ts">
	import { resolve } from '$app/paths';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import Progress from '$lib/components/Progress.svelte';
	import { serviceExamples } from '$lib/examples';
	import { isBranchStep } from '$lib/schema';

	const stages = [
		{ number: 1, label: 'Start', state: 'complete' as const },
		{ number: 2, label: 'Create', state: 'complete' as const },
		{ number: 3, label: 'Edit and review', state: 'current' as const },
		{ number: 4, label: 'Policy check', state: 'upcoming' as const },
		{ number: 5, label: 'Publish', state: 'upcoming' as const }
	];

	// Which example service is chosen here, before the graph editor itself is reached. The examples are
	// bundled and validated at build time, so this is just a slug into that list.
	let selectedSlug = $state(serviceExamples[0]?.slug ?? '');
	const selectedExample = $derived(serviceExamples.find((example) => example.slug === selectedSlug) ?? null);

	// Branch count uses the same predicate the graph editor itself uses to decide whether a step gets a
	// gateway diamond, so this count and the diagram never disagree about what counts as a branch.
	const branchCount = $derived(selectedExample?.service?.steps.filter(isBranchStep).length ?? 0);
</script>

<svelte:head>
	<title>Edit and review the journey | Service Studio</title>
</svelte:head>

<ServiceHeader />

<main class="picker-page">
	<Progress {stages} />

	<div class="picker-page__content govuk-!-padding-7">
		<h1 class="govuk-heading-xl">Edit and review the journey</h1>
		<p class="govuk-body">
			Choose a service below, then open the graph editor. The editor takes over the full canvas so you
			have more room to work with longer journeys.
		</p>

		<div class="govuk-form-group picker-page__select">
			<label class="govuk-label govuk-label--s" for="example-service">Choose a service</label>
			<select class="govuk-select" id="example-service" bind:value={selectedSlug}>
				{#each serviceExamples as example (example.slug)}
					<option value={example.slug}>{example.name}</option>
				{/each}
			</select>
		</div>

		{#if selectedExample && !selectedExample.service}
			<div class="govuk-error-summary" role="alert">
				<h2 class="govuk-error-summary__title">This example does not match the canonical schema</h2>
				<div class="govuk-error-summary__body">
					<ul class="govuk-list govuk-error-summary__list">
						{#each selectedExample.issues as issue, index (index)}
							<li>{issue.path}: {issue.message}</li>
						{/each}
					</ul>
				</div>
			</div>
		{:else if selectedExample?.service}
			<dl class="picker-page__stats">
				<div class="picker-page__stat">
					<dt class="govuk-heading-l govuk-!-margin-bottom-0">{selectedExample.service.steps.length}</dt>
					<dd class="govuk-body-s govuk-!-margin-bottom-0">steps</dd>
				</div>
				<div class="picker-page__stat">
					<dt class="govuk-heading-l govuk-!-margin-bottom-0">{branchCount}</dt>
					<dd class="govuk-body-s govuk-!-margin-bottom-0">{branchCount === 1 ? 'branch' : 'branches'}</dd>
				</div>
			</dl>

			<a class="govuk-button picker-page__open picker-page__open--blue" href={resolve('/edit/[slug]', { slug: selectedExample.slug })}>
				Open the graph editor
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
		gap: 2px;
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
