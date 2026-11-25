<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import ApiCallValues from '$lib/form-editor/components/ApiCallValues.svelte';
	import AssignValues from '$lib/form-editor/components/AssignValues.svelte';
	import WaitValues from '$lib/form-editor/components/WaitValues.svelte';
	import { techReviewSteps } from '$lib/form-editor/review-steps';
	import { saveReviewedForm } from '$lib/form-editor/review-draft';
	import { stateLabels, stateTagColours } from '$lib/form-editor/state-labels';
	import { developerSteps, stepValuesSummary, withEntryState } from '$lib/form-editor/step-values/step-values';
	import { techReviewProgress } from '$lib/form-editor/tech-review-progress.svelte';
	import type { WorkingState } from '$lib/schema/workflow/working-process';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// The developer steps in journey order, and how many have been marked as checked while the tab has been open.
	const steps = $derived(developerSteps(data.workflow));
	const isChecked = (code: string) => techReviewProgress.checkedSteps.includes(code);
	const checked = $derived(steps.filter((step) => isChecked(step.code)).length);
	const allChecked = $derived(checked === steps.length);

	// The step whose panel is open. Only one is open at a time, so the page does not grow too long.
	let openStep = $state<string>();

	/**
	 * Saves a step with its checked values into the draft, marks it as checked and closes its
	 * panel.
	 */
	async function saveChecked(code: string, state: WorkingState) {
		await saveReviewedForm(data.draft, withEntryState(data.workflow, code, state), 'Tech review');
		if (!isChecked(code)) techReviewProgress.checkedSteps.push(code);
		openStep = undefined;
		// The layout opened the form before the step was changed, so it is opened again to pick up the change.
		await invalidateAll();
	}
</script>

<svelte:head>
	<title>Step values: Technical review | Service Studio</title>
</svelte:head>

<ReviewStep
	steps={techReviewSteps(['complete', 'complete', 'current', 'upcoming'])}
	heading="Step values"
	hint={steps.length === 0
		? 'Only the steps a developer sets up are listed here.'
		: 'Only the steps a developer sets up are listed. Open each one to check its values.'}
>
	{#snippet status()}
		<p class="govuk-body govuk-!-font-weight-bold" class:step-values__checked={steps.length > 0 && allChecked}>
			{steps.length === 0 ? 'Nothing to check' : `${checked} of ${steps.length} checked`}
		</p>
	{/snippet}

	{#if steps.length === 0}
		<div class="step-values__empty">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-2">No developer steps found</h3>
			<p class="govuk-body govuk-!-margin-bottom-0">This journey has no API calls, assign steps or waits, so there is nothing to check.</p>
		</div>
	{:else}
		<table class="govuk-table step-values__table">
			<caption class="govuk-visually-hidden">Developer steps and whether their values have been checked</caption>
			<thead class="govuk-table__head">
				<tr class="govuk-table__row">
					<th scope="col" class="govuk-table__header step-values__step-cell">Step</th>
					<th scope="col" class="govuk-table__header">Details</th>
					<th scope="col" class="govuk-table__header">Values</th>
					<th scope="col" class="govuk-table__header step-values__status-cell">Status</th>
				</tr>
			</thead>
			<tbody class="govuk-table__body">
				{#each steps as step (step.code)}
					{@const open = openStep === step.code}
					<tr class="govuk-table__row" class:step-values__row--open={open}>
						<td class="govuk-table__cell step-values__step-cell">
							<strong class="govuk-tag govuk-tag--{stateTagColours[step.state.state_type]}">{stateLabels[step.state.state_type]}</strong>
						</td>
						<td class="govuk-table__cell">
							<button
								class="step-values__toggle govuk-link"
								class:govuk-!-font-weight-bold={open}
								type="button"
								aria-expanded={open}
								aria-controls="step-values-{step.code}"
								onclick={() => (openStep = open ? undefined : step.code)}
							>
								{step.title}
							</button>
						</td>
						<td class="govuk-table__cell step-values__summary">{stepValuesSummary(step.state)}</td>
						<td class="govuk-table__cell step-values__status-cell govuk-!-font-weight-bold">
							{#if isChecked(step.code)}
								<span class="step-values__checked">Checked</span>
							{:else}
								<span class="step-values__to-check">To check</span>
							{/if}
						</td>
					</tr>
					{#if open}
						<tr class="govuk-table__row" id="step-values-{step.code}">
							<td class="govuk-table__cell step-values__panel" colspan="4">
								{#if step.state.state_type === 'api_call'}
									<ApiCallValues code={step.code} title={step.title} state={step.state} onchecked={(state) => saveChecked(step.code, state)} />
								{:else if step.state.state_type === 'assign'}
									<AssignValues title={step.title} state={step.state} onchecked={(state) => saveChecked(step.code, state)} />
								{:else if step.state.state_type === 'wait'}
									<WaitValues title={step.title} state={step.state} onchecked={(state) => saveChecked(step.code, state)} />
								{/if}
							</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
	{/if}

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/tech-review/form/flex')}>Back</a>
		{#if allChecked}
			<a class="govuk-button govuk-!-margin-bottom-0" href={resolve('/tech-review/form/review')}>Continue to review</a>
		{:else}
			<button class="govuk-button govuk-!-margin-bottom-0" type="button" disabled aria-disabled="true" aria-describedby="check-to-continue">
				Continue to review
			</button>
			<p class="govuk-body govuk-!-margin-bottom-0" id="check-to-continue">Check every developer step to continue</p>
		{/if}
	{/snippet}
</ReviewStep>

<style>
	.step-values__checked {
		color: #00703c;
	}

	.step-values__to-check {
		color: #7a3c1c;
	}

	/* A heavier rule under the headings, as in the design, marks where the rows start. */
	.step-values__table th {
		border-bottom: 2px solid #0b0c0c;
	}

	.step-values__table td {
		vertical-align: middle;
	}

	/* The Step column only holds the tag for the kind of step, so it is kept as narrow as the tag. */
	.step-values__step-cell {
		width: 1%;
		white-space: nowrap;
	}

	.step-values__status-cell {
		width: 110px;
	}

	/* The values are written as they are in the schema, so they are set in a fixed width font. */
	.step-values__summary {
		font-family: ui-monospace, Menlo, Consolas, monospace;
		font-size: 1rem;
		color: #505a5f;
		overflow-wrap: anywhere;
	}

	/* The step's title opens its panel. It is a button so it is read out as one, drawn as a link. */
	.step-values__toggle {
		padding: 0;
		font-family: inherit;
		font-size: inherit;
		line-height: inherit;
		text-align: left;
		background: none;
		border: 0;
		cursor: pointer;
	}

	/* The open row and its panel are shaded together, so it is clear which step the fields belong to. */
	.step-values__row--open td {
		border-bottom: 0;
	}

	.step-values__row--open,
	.step-values__panel {
		background-color: #f3f8fc;
	}

	.step-values__panel {
		padding: 20px;
	}

	.step-values__empty {
		padding: 20px 25px;
		background-color: #f3f2f1;
		border-left: 5px solid #505a5f;
	}
</style>
