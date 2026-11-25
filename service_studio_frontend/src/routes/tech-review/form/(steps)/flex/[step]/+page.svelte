<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { bodyForEndpoint, summariseBody, usesEndpoint, withEndpoint, type FlexEndpoint } from '$lib/form-editor/flex-connections';
	import { placeholderEndpoints } from '$lib/form-editor/placeholder-endpoints';
	import { techReviewSteps } from '$lib/form-editor/review-steps';
	import { saveReviewedForm } from '$lib/form-editor/review-draft';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// The endpoint chosen on this page. It starts as the one the call is already connected to, if any, and changes
	// when another is selected. Nothing is written into the form until "Use this endpoint" is pressed.
	let selected = $derived<FlexEndpoint | undefined>(placeholderEndpoints.find((endpoint) => usesEndpoint(data.call, endpoint)));

	// The body the chosen endpoint would give the call. It is empty for an endpoint that takes no body, which hides the
	// Body line of the panel.
	const body = $derived(selected && bodyForEndpoint(data.call.body, selected));
	const bodySummary = $derived(body && summariseBody(body));

	/**
	 * Writes the chosen endpoint into the API call step, saves the draft and goes back to the list
	 * of Flex connections, which then shows the call as connected.
	 */
	async function useEndpoint() {
		if (!selected) return;
		await saveReviewedForm(data.draft, { stage: 'Tech review', workflow: withEndpoint(data.workflow, data.call.code, selected) });
		// The layout opened the form before the call was changed, so it is opened again to pick up the change.
		await goto(resolve('/tech-review/form/flex'), { invalidateAll: true });
	}
</script>

<svelte:head>
	<title>Find the endpoint for {data.call.title}: Technical review | Service Studio</title>
</svelte:head>

<ReviewStep steps={techReviewSteps(['complete', 'current', 'upcoming', 'upcoming'])}>
	<a class="govuk-back-link govuk-!-margin-top-0" href={resolve('/tech-review/form/flex')}>Back to Flex connections</a>
	<h2 class="govuk-heading-l">Find the endpoint for {data.call.title}</h2>

	<!-- Search and the filters are shown so the design is complete. They work once the real Flex list is connected. -->
	<div class="govuk-form-group">
		<label class="govuk-label govuk-visually-hidden" for="endpoint-search">Search for an endpoint</label>
		<div class="govuk-hint" id="endpoint-search-hint">Search and filters work once the Flex list is connected. These are example endpoints.</div>
		<input class="govuk-input" id="endpoint-search" type="search" aria-describedby="endpoint-search-hint" disabled />
	</div>

	<div class="find-endpoint__filters govuk-!-margin-bottom-6">
		<span class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">Narrow by</span>
		<div class="find-endpoint__filter">
			<label class="govuk-label govuk-!-margin-bottom-0" for="endpoint-service">Service</label>
			<select class="govuk-select" id="endpoint-service" disabled>
				<option>All services</option>
			</select>
		</div>
		<div class="find-endpoint__filter">
			<label class="govuk-label govuk-!-margin-bottom-0" for="endpoint-method">Method</label>
			<select class="govuk-select" id="endpoint-method" disabled>
				<option>All methods</option>
			</select>
		</div>
		<div class="govuk-checkboxes govuk-checkboxes--small">
			<div class="govuk-checkboxes__item">
				<input class="govuk-checkboxes__input" id="hide-deprecated" type="checkbox" disabled />
				<label class="govuk-label govuk-checkboxes__label" for="hide-deprecated">Hide deprecated</label>
			</div>
		</div>
		<a class="govuk-link" role="link" aria-disabled="true">Clear filters</a>
	</div>

	<p class="govuk-body">Showing {placeholderEndpoints.length} of {placeholderEndpoints.length} endpoints</p>

	<table class="govuk-table find-endpoint__results">
		<caption class="govuk-visually-hidden">Endpoints</caption>
		<thead class="govuk-table__head">
			<tr class="govuk-table__row">
				<th scope="col" class="govuk-table__header">Method</th>
				<th scope="col" class="govuk-table__header">Url</th>
				<th scope="col" class="govuk-table__header">What it does</th>
				<th scope="col" class="govuk-table__header">Service</th>
				<th scope="col" class="govuk-table__header"><span class="govuk-visually-hidden">Choose</span></th>
			</tr>
		</thead>
		<tbody class="govuk-table__body">
			{#each placeholderEndpoints as endpoint (`${endpoint.method} ${endpoint.url}`)}
				{@const isSelected = selected === endpoint}
				<tr class="govuk-table__row" class:find-endpoint__row--selected={isSelected} class:find-endpoint__row--deprecated={endpoint.deprecated}>
					<td class="govuk-table__cell find-endpoint__code govuk-!-font-weight-bold">{endpoint.method}</td>
					<td class="govuk-table__cell">
						<span class="find-endpoint__code">{endpoint.url}</span>
						{#if endpoint.deprecated}
							<strong class="govuk-tag govuk-tag--grey">Deprecated</strong>
						{/if}
					</td>
					<td class="govuk-table__cell">{endpoint.description}</td>
					<td class="govuk-table__cell">{endpoint.service}</td>
					<td class="govuk-table__cell find-endpoint__choose">
						{#if isSelected}
							<span class="govuk-!-font-weight-bold find-endpoint__selected">Selected</span>
						{:else}
							<button class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0" type="button" onclick={() => (selected = endpoint)}>
								Select<span class="govuk-visually-hidden"> {endpoint.method} {endpoint.url}</span>
							</button>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>

	<!-- What the chosen endpoint writes into the step, read out when it changes. -->
	<div class="find-endpoint__fills-in" aria-live="polite">
		<div>
			<h3 class="govuk-heading-s govuk-!-margin-bottom-1">Fills in for {data.call.title}</h3>
			<p class="govuk-hint govuk-!-margin-bottom-0">You can still change these in step values.</p>
		</div>
		{#if selected}
			<dl class="find-endpoint__values">
				<div>
					<dt class="govuk-hint govuk-!-margin-bottom-0">Method</dt>
					<dd class="find-endpoint__code">{selected.method}</dd>
				</div>
				<div>
					<dt class="govuk-hint govuk-!-margin-bottom-0">Service</dt>
					<dd class="find-endpoint__code">{selected.service}</dd>
				</div>
				<div>
					<dt class="govuk-hint govuk-!-margin-bottom-0">Url</dt>
					<dd class="find-endpoint__code">{selected.url}</dd>
				</div>
				{#if bodySummary}
					<div>
						<dt class="govuk-hint govuk-!-margin-bottom-0">Body</dt>
						<dd class="find-endpoint__code">
							{bodySummary.fields} {bodySummary.fields === 1 ? 'field' : 'fields'}{bodySummary.toFillIn > 0 ? `, ${bodySummary.toFillIn} to fill in` : ''}
						</dd>
					</div>
				{/if}
			</dl>
		{:else}
			<p class="govuk-body govuk-!-margin-bottom-0">Select an endpoint to see what it fills in.</p>
		{/if}
	</div>

	{#snippet actions()}
		<button class="govuk-button govuk-!-margin-bottom-0" type="button" disabled={!selected} onclick={useEndpoint}>Use this endpoint</button>
		<a class="govuk-link" href={resolve('/tech-review/form/flex')}>Cancel</a>
	{/snippet}
</ReviewStep>

<style>
	/* The filters sit in one row beside their labels, and wrap onto more lines on a narrow screen. */
	.find-endpoint__filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 15px 30px;
	}

	/* GOV.UK caps a checkbox label at the width of its group less the box, but here the group is only as wide as its
		label, so the cap would always fold "Hide deprecated" onto two lines. Lifting the cap lets it sit on one. */
	.find-endpoint__filters :global(.govuk-checkboxes__label) {
		max-width: none;
	}

	.find-endpoint__filter {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	/* A heavier rule under the headings, as in the design, marks where the rows start. */
	.find-endpoint__results th {
		border-bottom: 2px solid #0b0c0c;
	}

	.find-endpoint__results td {
		vertical-align: middle;
	}

	/* Methods, urls and service names are written as they are in the schema, so they are set in a fixed width font. */
	.find-endpoint__code {
		font-family: ui-monospace, Menlo, Consolas, monospace;
		font-size: 1rem;
		overflow-wrap: anywhere;
	}

	.find-endpoint__row--selected {
		background-color: #f3f8fc;
	}

	.find-endpoint__row--deprecated td {
		color: #505a5f;
	}

	.find-endpoint__choose {
		text-align: right;
		white-space: nowrap;
	}

	.find-endpoint__selected {
		color: #1d70b8;
	}

	/* A panel marked down its left side that shows what the chosen endpoint will write into the step. */
	.find-endpoint__fills-in {
		display: flex;
		flex-wrap: wrap;
		gap: 20px 50px;
		padding: 25px 30px;
		background-color: #f3f2f1;
		border-left: 5px solid #1d70b8;
	}

	.find-endpoint__values {
		display: flex;
		flex-wrap: wrap;
		gap: 15px 40px;
		margin: 0;
	}

	.find-endpoint__values dd {
		margin: 0;
	}
</style>
