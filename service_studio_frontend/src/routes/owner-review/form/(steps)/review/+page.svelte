<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { exampleProblems, flexConnections, journeySteps, problemCount, type CheckResult } from '$lib/form-editor/owner-review-checks';
	import { ownerReviewProgress } from '$lib/form-editor/owner-review-progress.svelte';
	import { ownerReviewSteps } from '$lib/form-editor/owner-review-steps';
	import { stateLabels } from '$lib/form-editor/state-labels';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const process = $derived(data.workflow.processes[data.workflow.manifest.entry]);
	const steps = $derived(journeySteps(process));
	const connections = $derived(flexConnections(process));

	// The problems found by the checks. Until the tech review is built there are no real checks, so this is empty
	// unless the example problems are switched on.
	const problems = $derived(ownerReviewProgress.showExampleProblems ? exampleProblems(steps) : []);
	const problemsByState = $derived(new Map(problems.map((problem) => [problem.stateId, problem.result])));
	const summary = $derived(problemCount(problems));

	// Sign off waits for the tech review to finish and for every error to be fixed. The example problems stand for a
	// tech review that is not finished, so they stop sign off too.
	const canSignOff = $derived(problems.length === 0);

	// When the checks last ran. They are not real yet, so this is when the page was opened.
	const checkedAt = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

	// Goes on to sign off. Getting this far means the owner has read the journey and the checks, which the sign off
	// checklist records.
	function continueToSignOff() {
		ownerReviewProgress.journeyRead = true;
		goto(resolve('/owner-review/form/sign-off'));
	}

	// The words and GOV.UK tag colour for each result.
	const results: Record<CheckResult, { tag: string; colour: string; inRow: string }> = {
		error: { tag: 'Error', colour: 'red', inRow: '1 error' },
		warning: { tag: 'Warning', colour: 'yellow', inRow: '1 warning' },
		pending: { tag: 'Pending', colour: 'grey', inRow: 'Check pending' }
	};
</script>

<svelte:head>
	<title>Review: Owner review | Service Studio</title>
</svelte:head>

<ReviewStep
	steps={ownerReviewSteps(['complete', canSignOff ? 'current' : 'problem', 'upcoming'])}
	heading="Review"
	hint="Check the technical review, clear any validation problems and look through the journey."
>
	{#snippet status()}
		<p class="govuk-body govuk-!-font-weight-bold review__status review__status--{canSignOff ? 'clear' : 'problem'}">
			{canSignOff ? 'All checks clear' : summary}
		</p>

		<!-- A switch for seeing the design with problems, until the tech review gives the real checks. -->
		<div class="govuk-checkboxes govuk-checkboxes--small govuk-!-margin-top-6">
			<div class="govuk-checkboxes__item">
				<input
					class="govuk-checkboxes__input"
					id="example-problems"
					type="checkbox"
					aria-describedby="example-problems-hint"
					bind:checked={ownerReviewProgress.showExampleProblems}
				/>
				<label class="govuk-label govuk-checkboxes__label" for="example-problems">Show example problems</label>
				<div id="example-problems-hint" class="govuk-hint govuk-checkboxes__hint">
					For design only. The real checks come from the tech review.
				</div>
			</div>
		</div>
	{/snippet}

	<section aria-labelledby="technical-review">
		<div class="review__section-heading" class:review__fact-columns={canSignOff}>
			<h2 class="govuk-heading-m govuk-!-margin-bottom-0" id="technical-review">Technical review</h2>
			<span class="review__status review__status--{canSignOff ? 'clear' : 'unfinished'}">
				{canSignOff ? 'Complete' : 'Not finished'}
			</span>
			{#if canSignOff}
				<a class="govuk-link review__heading-link" href={resolve('/tech-review/form')}>View technical review</a>
			{/if}
		</div>

		{#if canSignOff}
			<!-- The run timeout and the step values are examples until the tech review records them. -->
			<dl class="review__facts review__fact-columns">
				<div>
					<dt class="govuk-body-s govuk-!-margin-bottom-0 review__fact-label">Workflow settings</dt>
					<dd class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">Set, 7 day run timeout</dd>
				</div>
				<div>
					<dt class="govuk-body-s govuk-!-margin-bottom-0 review__fact-label">Flex connections</dt>
					<dd class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">
						{connections.connected} of {connections.total} connected
					</dd>
				</div>
				<div>
					<dt class="govuk-body-s govuk-!-margin-bottom-0 review__fact-label">Step values</dt>
					<dd class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">{steps.length} of {steps.length} checked</dd>
				</div>
			</dl>
		{:else}
			<div class="review__panel review__panel--unfinished">
				<div>
					<p class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-1">Some steps still need checking</p>
					<p class="govuk-body govuk-!-margin-bottom-0">
						The developer has not marked every step as checked. Sign off stays locked until they finish.
					</p>
				</div>
				<a class="govuk-button govuk-!-margin-bottom-0" href={resolve('/tech-review/form')}>Go back to technical review</a>
			</div>
		{/if}
	</section>

	<hr class="govuk-section-break govuk-section-break--l govuk-section-break--visible" />

	<section aria-labelledby="validation-checks">
		<div class="review__section-heading">
			<h2 class="govuk-heading-m govuk-!-margin-bottom-0" id="validation-checks">Validation checks</h2>
			<span class="review__status review__status--{canSignOff ? 'clear' : 'problem'}">{canSignOff ? 'Clear' : summary}</span>
		</div>

		{#if problems.length === 0}
			<div class="review__panel review__panel--clear">
				<div>
					<p class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-1">No errors or warnings</p>
					<p class="govuk-body govuk-!-margin-bottom-0 review__muted">All {steps.length} steps checked today at {checkedAt}.</p>
				</div>
			</div>
		{:else}
			<table class="govuk-table govuk-!-margin-bottom-0 review__checks">
				<caption class="govuk-visually-hidden">Problems found by the checks</caption>
				<thead class="govuk-visually-hidden">
					<tr>
						<th scope="col">Result</th>
						<th scope="col">Problem</th>
						<th scope="col">Action</th>
					</tr>
				</thead>
				<tbody class="govuk-table__body">
					{#each problems as problem (problem.stateId)}
						<tr class="govuk-table__row">
							<td class="govuk-table__cell review__result-cell">
								<strong class="govuk-tag govuk-tag--{results[problem.result].colour}">{results[problem.result].tag}</strong>
							</td>
							<td class="govuk-table__cell">{problem.message}</td>
							<td class="govuk-table__cell review__action-cell">
								{#if problem.result === 'pending'}
									<span class="review__muted">Running</span>
								{:else}
									<a class="govuk-link" role="link" aria-disabled="true">Open step in editor</a>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</section>

	<hr class="govuk-section-break govuk-section-break--l govuk-section-break--visible" />

	<section aria-labelledby="citizen-journey">
		<div class="review__section-heading">
			<h2 class="govuk-heading-m govuk-!-margin-bottom-0" id="citizen-journey">Citizen journey</h2>
			<span class="govuk-body govuk-!-margin-bottom-0 review__muted">
				Read only · {steps.length} steps{#if canSignOff}&nbsp;· <span class="review__status review__status--clear">All clear</span>{/if}
			</span>
			<span class="govuk-body-s govuk-!-margin-bottom-0 review__muted review__heading-link">Scroll for the rest</span>
		</div>

		<!-- A long journey scrolls inside its own box, so the checks above stay close to the buttons below. -->
		<div class="review__journey" class:review__journey--clear={canSignOff} role="region" aria-labelledby="citizen-journey" tabindex="-1">
			<table class="govuk-table govuk-!-margin-bottom-0">
				<caption class="govuk-visually-hidden">Steps in the citizen journey</caption>
				<thead class="govuk-visually-hidden">
					<tr>
						<th scope="col">Number</th>
						<th scope="col">Step</th>
						<th scope="col">Kind</th>
						<th scope="col">Checks</th>
					</tr>
				</thead>
				<tbody class="govuk-table__body">
					{#each steps as step (step.stateId)}
						{@const result = problemsByState.get(step.stateId)}
						<tr class="govuk-table__row review__step" class:review__step--error={result === 'error'} class:review__step--warning={result === 'warning'} class:review__step--pending={result === 'pending'}>
							<td class="govuk-table__cell review__step-number">{step.number}</td>
							<td class="govuk-table__cell" class:govuk-!-font-weight-bold={result}>{step.title}</td>
							<td class="govuk-table__cell review__step-kind review__muted">{stateLabels[step.stateType]}</td>
							<td class="govuk-table__cell review__step-check">
								{#if result}
									<span class="review__check review__check--{result}">
										<span class="review__check-icon" aria-hidden="true">{result === 'pending' ? '' : '!'}</span>
										{results[result].inRow}
									</span>
								{:else}
									<span class="review__check" class:review__check--clear={canSignOff}>No issues</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/owner-review/form')}>Back</a>
		<button
			class="govuk-button govuk-!-margin-bottom-0"
			type="button"
			disabled={!canSignOff}
			onclick={continueToSignOff}
		>
			Continue to sign off
		</button>
		<a class="govuk-link" role="link" aria-disabled="true">Save for later</a>
		{#if !canSignOff}
			<p class="govuk-body govuk-!-margin-bottom-0 review__muted">Finish the technical review and fix the error to continue</p>
		{/if}
	{/snippet}
</ReviewStep>

<style>
	/* A section heading has its status beside it, and a link or a note pushed to the far side. */
	.review__section-heading {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 15px;
		margin-bottom: 15px;
	}

	.review__heading-link {
		margin-left: auto;
	}

	.review__status {
		font-family: 'GDS Transport', arial, sans-serif;
		font-size: 1rem;
		font-weight: 700;
	}

	.review__status--clear {
		color: #00703c;
	}

	.review__status--problem {
		color: #d4351c;
	}

	.review__status--unfinished {
		color: #7a3c1c;
	}

	.review__muted {
		color: #505a5f;
	}

	.review__facts {
		margin: 0;
	}

	/* The heading row and the facts under it share the same columns, so the status beside the heading starts where
		the second fact does. */
	.review__fact-columns {
		display: grid;
		grid-template-columns: 240px 240px 1fr;
		column-gap: 30px;
	}

	@media (max-width: 640px) {
		.review__fact-columns {
			grid-template-columns: 1fr;
			row-gap: 15px;
		}
	}

	.review__facts dd {
		margin: 0;
	}

	.review__fact-label {
		color: #505a5f;
	}

	/* A panel that says where a whole section stands, marked by a coloured rule down its left side. */
	.review__panel {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 20px;
		padding: 20px 25px;
		border-left: 5px solid;
	}

	.review__panel--unfinished {
		background-color: #fff7bf;
		border-left-color: #ffdd00;
	}

	.review__panel--clear {
		background-color: #f3f2f1;
		border-left-color: #00703c;
	}

	.review__checks {
		border-top: 2px solid #0b0c0c;
	}

	/* A fixed width keeps the tags lined up, whatever their words. */
	.review__result-cell {
		width: 100px;
	}

	.review__action-cell {
		white-space: nowrap;
		text-align: right;
	}

	.review__journey {
		max-height: 400px;
		overflow-y: auto;
		border: 1px solid #b1b4b6;
	}

	.review__journey--clear {
		border-color: #00703c;
		border-left-width: 5px;
	}

	/* Cells are centred in the row, as the result marks have no text of their own to line up by. */
	.review__step td {
		padding: 10px 15px;
		vertical-align: middle;
	}

	.review__step-number {
		width: 30px;
		font-weight: 700;
		color: #505a5f;
	}

	.review__step-kind {
		width: 100px;
	}

	.review__step-check {
		width: 160px;
	}

	/* A step with a problem is shaded and marked down its left side in the colour of its result. */
	.review__step--error {
		background-color: #fcedea;
		box-shadow: inset 5px 0 0 #d4351c;
	}

	.review__step--warning {
		background-color: #fff7bf;
		box-shadow: inset 5px 0 0 #ffdd00;
	}

	.review__step--pending {
		background-color: #f3f2f1;
		box-shadow: inset 5px 0 0 #505a5f;
	}

	.review__check {
		color: #505a5f;
		white-space: nowrap;
	}

	.review__check--clear,
	.review__check--error,
	.review__check--warning,
	.review__check--pending {
		font-weight: 700;
	}

	.review__check--clear {
		color: #00703c;
	}

	.review__check--error {
		color: #d4351c;
	}

	.review__check--warning {
		color: #0b0c0c;
	}

	/* A small round mark before the result, filled for a problem and empty for a check that is still running. Middle
		alignment centres it on the height of the small letters beside it, which is where the eye reads the middle of
		the words. Centring on the line box instead puts it too low, because the font sits high in its line. */
	.review__check-icon {
		display: inline-flex;
		margin-right: 5px;
		vertical-align: middle;
		align-items: center;
		justify-content: center;
		box-sizing: border-box;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		font-size: 0.875rem;
		font-weight: 700;
		line-height: 1;
	}

	.review__check--error .review__check-icon {
		background-color: #d4351c;
		color: #ffffff;
	}

	.review__check--warning .review__check-icon {
		background-color: #ffdd00;
		color: #0b0c0c;
	}

	.review__check--pending .review__check-icon {
		border: 2px solid #505a5f;
	}
</style>
