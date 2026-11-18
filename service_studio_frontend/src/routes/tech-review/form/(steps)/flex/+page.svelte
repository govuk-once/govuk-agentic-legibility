<script lang="ts">
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { apiCallSteps } from '$lib/form-editor/flex-connections';
	import { stateLabels, stateTagColours } from '$lib/form-editor/state-labels';
	import { techReviewSteps } from '$lib/form-editor/review-steps';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// The API calls in journey order, and how many are connected, which decides which of the three views is shown.
	const steps = $derived(apiCallSteps(data.workflow.processes[data.workflow.manifest.entry]));
	const connected = $derived(steps.filter((step) => step.connected).length);
	const allConnected = $derived(connected === steps.length);
</script>

<svelte:head>
	<title>Flex connections: Technical review | Service Studio</title>
</svelte:head>

<ReviewStep
	steps={techReviewSteps(['complete', 'current', 'upcoming', 'upcoming'])}
	heading="Flex connections"
	hint={steps.length === 0
		? 'Only steps that call an API can connect to Flex.'
		: allConnected
			? 'Every API call step now has an endpoint.'
			: `We found ${steps.length} ${steps.length === 1 ? 'step that calls' : 'steps that call'} an API. Connect each one to a Flex endpoint and the method, service, url and body fill in for you.`}
>
	{#snippet status()}
		{#if steps.length === 0}
			<p class="govuk-body govuk-!-font-weight-bold">Nothing to connect</p>
		{:else if allConnected}
			<p class="govuk-body govuk-!-font-weight-bold flex-connections__connected">All connected</p>
		{:else}
			<p class="govuk-body govuk-!-font-weight-bold">{connected} of {steps.length} connected</p>
		{/if}
	{/snippet}

	{#if steps.length === 0}
		<div class="flex-connections__panel flex-connections__panel--empty">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-2">No API call steps found</h3>
			<p class="govuk-body govuk-!-margin-bottom-0">This journey has no steps that call an API, so there is nothing to connect.</p>
		</div>
		<p class="govuk-hint govuk-!-margin-top-4">If you add an API call step later, it will appear here and this stage will ask you to connect it.</p>
	{:else}
		{#if allConnected}
			<div class="flex-connections__panel flex-connections__panel--connected govuk-!-margin-bottom-6">
				<h3 class="govuk-heading-s govuk-!-margin-bottom-2 flex-connections__connected">
					{steps.length === 1 ? 'The API call is connected' : `All ${steps.length} API calls are connected`}
				</h3>
				<p class="govuk-body govuk-!-margin-bottom-0">Check the values for each in the next stage.</p>
			</div>
		{/if}

		<table class="govuk-table govuk-!-margin-bottom-4 flex-connections__table">
			<caption class="govuk-visually-hidden">API call steps and their Flex connections</caption>
			<thead class="govuk-table__head">
				<tr class="govuk-table__row">
					<th scope="col" class="govuk-table__header flex-connections__step-cell">Step</th>
					<th scope="col" class="govuk-table__header">Details</th>
					<th scope="col" class="govuk-table__header flex-connections__status-cell">Status</th>
					<th scope="col" class="govuk-table__header flex-connections__action-cell"><span class="govuk-visually-hidden">Action</span></th>
				</tr>
			</thead>
			<tbody class="govuk-table__body">
				{#each steps as step (step.code)}
					<tr class="govuk-table__row" class:flex-connections__row--unconnected={!step.connected}>
						<td class="govuk-table__cell flex-connections__step-cell">
							<strong class="govuk-tag govuk-tag--{stateTagColours[step.stateType]}">{stateLabels[step.stateType]}</strong>
						</td>
						<td class="govuk-table__cell">
							<span class="govuk-!-display-block">{step.title}</span>
							{#if step.connected}
								<span class="flex-connections__address">{step.method} {step.url}</span>
							{:else}
								<span class="govuk-hint govuk-!-margin-bottom-0">No endpoint chosen yet</span>
							{/if}
						</td>
						<td class="govuk-table__cell flex-connections__status-cell">
							<span class="govuk-!-font-weight-bold" class:flex-connections__connected={step.connected} class:flex-connections__unconnected={!step.connected}>
								{step.connected ? 'Connected' : 'Needs connecting'}
							</span>
						</td>
						<td class="govuk-table__cell flex-connections__action-cell">
							{#if step.connected}
								<a class="govuk-link" href={resolve('/tech-review/form/(steps)/flex/[step]', { step: step.code })}>
									Change<span class="govuk-visually-hidden"> the endpoint for {step.title}</span>
								</a>
							{:else}
								<a class="govuk-button govuk-!-margin-bottom-0" href={resolve('/tech-review/form/(steps)/flex/[step]', { step: step.code })}>
									Find endpoint<span class="govuk-visually-hidden"> for {step.title}</span>
								</a>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>

		{#if !allConnected}
			<p class="govuk-hint">Steps that are not API calls do not need a Flex connection, so they are not listed here.</p>
		{/if}
	{/if}

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/tech-review/form')}>Back</a>
		{#if allConnected}
			<a class="govuk-button govuk-!-margin-bottom-0" href={resolve('/tech-review/form/step-values')}>Continue to step values</a>
		{:else}
			<button class="govuk-button govuk-!-margin-bottom-0" type="button" disabled aria-disabled="true" aria-describedby="connect-to-continue">
				Continue to step values
			</button>
			<p class="govuk-body govuk-!-margin-bottom-0" id="connect-to-continue">Connect every API call to continue</p>
		{/if}
	{/snippet}
</ReviewStep>

<style>
	.flex-connections__connected {
		color: #00703c;
	}

	.flex-connections__unconnected {
		color: #7a3c1c;
	}

	/* A panel that says where the whole list stands, marked by a coloured rule down its left side. */
	.flex-connections__panel {
		padding: 20px 25px;
		border-left: 5px solid;
	}

	.flex-connections__panel--connected {
		background-color: #e6f0eb;
		border-left-color: #00703c;
	}

	.flex-connections__panel--empty {
		background-color: #f3f2f1;
		border-left-color: #505a5f;
	}

	/* A heavier rule under the headings, as in the design, marks where the rows start. */
	.flex-connections__table th {
		border-bottom: 2px solid #0b0c0c;
	}

	.flex-connections__table td {
		vertical-align: middle;
	}

	/* A call that still needs connecting is shaded, so the rows that need work stand out. */
	.flex-connections__row--unconnected {
		background-color: #f3f8fc;
	}

	/* The method and url are written as they are in the schema, so they are set in a fixed width font. */
	.flex-connections__address {
		font-family: ui-monospace, Menlo, Consolas, monospace;
		font-size: 1rem;
		color: #505a5f;
		overflow-wrap: anywhere;
	}

	/* The Step column only holds the tag for the kind of step, so it is kept as narrow as the tag. */
	.flex-connections__step-cell {
		width: 1%;
		white-space: nowrap;
	}

	.flex-connections__status-cell {
		width: 170px;
	}

	.flex-connections__action-cell {
		width: 160px;
		text-align: right;
		white-space: nowrap;
	}
</style>
