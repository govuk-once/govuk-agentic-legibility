<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { apiCallSteps } from '$lib/form-editor/flex-connections';
	import { techReviewSteps } from '$lib/form-editor/review-steps';
	import { saveFormForReview } from '$lib/form-editor/review-store';
	import { developerSteps, stepValuesSummary, withTechReviewChecked } from '$lib/form-editor/step-values/step-values';
	import { techReviewProgress } from '$lib/form-editor/tech-review-progress.svelte';
	import { describeWorkflowSettings } from '$lib/form-editor/tech-review-summary';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const settings = $derived(describeWorkflowSettings(data.workflow.manifest));
	const calls = $derived(apiCallSteps(data.workflow.processes[data.workflow.manifest.entry]));
	const steps = $derived(developerSteps(data.workflow));

	// The review can be sent once every API call is connected and every developer step has been marked as checked.
	const allConnected = $derived(calls.every((call) => call.connected));
	const allChecked = $derived(steps.every((step) => techReviewProgress.checkedSteps.includes(step.code)));
	const ready = $derived(allConnected && allChecked);

	/**
	 * Writes the time of sending into every developer step, keeps the form in the browser tab and goes back to the
	 * owner review, which reads those times to show the technical review as complete so the owner can sign off.
	 */
	async function sendForOwnerReview() {
		saveFormForReview(withTechReviewChecked(data.workflow, new Date().toISOString()));
		// The owner review opens the form again when it loads, so it picks up the times just written.
		await goto(resolve('/owner-review/form/review'));
	}
</script>

<svelte:head>
	<title>Review and send: Technical review | Service Studio</title>
</svelte:head>

<ReviewStep
	steps={techReviewSteps(['complete', 'complete', 'complete', ready ? 'current' : 'problem'])}
	heading="Review and send"
	hint={ready
		? 'Everything is set up. Check the summary, then send the form back to the service owner to sign off.'
		: 'Some of the technical review is not finished. Use the Change links to finish it, then send the form for review.'}
>
	{#snippet status()}
		<p class="govuk-body govuk-!-font-weight-bold" class:review-and-send__ready={ready}>{ready ? 'Ready to send' : 'Not ready to send'}</p>
	{/snippet}

	<dl class="govuk-summary-list review-and-send">
		<div class="govuk-summary-list__row">
			<dt class="govuk-summary-list__key">
				Workflow settings
				<a class="govuk-link govuk-!-display-block govuk-!-font-weight-regular" href={resolve('/tech-review/form')}>
					Change<span class="govuk-visually-hidden"> workflow settings</span>
				</a>
			</dt>
			<dd class="govuk-summary-list__value">
				<p class="govuk-body govuk-!-margin-bottom-1">Run timeout {settings.runTimeout}</p>
				<p class="govuk-body govuk-!-margin-bottom-0">API calls: {settings.apiCalls}</p>
			</dd>
		</div>

		<div class="govuk-summary-list__row">
			<dt class="govuk-summary-list__key">
				Flex connections
				<a class="govuk-link govuk-!-display-block govuk-!-font-weight-regular" href={resolve('/tech-review/form/flex')}>
					Change<span class="govuk-visually-hidden"> Flex connections</span>
				</a>
			</dt>
			<dd class="govuk-summary-list__value">
				{#if calls.length === 0}
					<p class="govuk-body govuk-!-margin-bottom-0">No API calls to connect</p>
				{:else}
					<ul class="govuk-list govuk-!-margin-bottom-0">
						{#each calls as call (call.code)}
							<li>
								{call.title} ·
								{#if call.connected}
									<span class="review-and-send__code">{call.method} {call.url}</span>
								{:else}
									<strong class="review-and-send__to-do">Needs connecting</strong>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</dd>
		</div>

		<div class="govuk-summary-list__row">
			<dt class="govuk-summary-list__key">
				Step values
				<a class="govuk-link govuk-!-display-block govuk-!-font-weight-regular" href={resolve('/tech-review/form/step-values')}>
					Change<span class="govuk-visually-hidden"> step values</span>
				</a>
			</dt>
			<dd class="govuk-summary-list__value">
				{#if steps.length === 0}
					<p class="govuk-body govuk-!-margin-bottom-0">No developer steps to check</p>
				{:else}
					<ul class="govuk-list govuk-!-margin-bottom-0">
						{#each steps as step (step.code)}
							<li>
								{step.title} ·
								<span class="review-and-send__code">{stepValuesSummary(step.state)}</span>
								{#if !techReviewProgress.checkedSteps.includes(step.code)}
									· <strong class="review-and-send__to-do">To check</strong>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</dd>
		</div>
	</dl>

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/tech-review/form/step-values')}>Back</a>
		{#if ready}
			<button class="govuk-button govuk-!-margin-bottom-0" type="button" onclick={sendForOwnerReview}>Send for sign off</button>
		{:else}
			<button class="govuk-button govuk-!-margin-bottom-0" type="button" disabled aria-disabled="true" aria-describedby="finish-to-send">
				Send for sign off
			</button>
			<p class="govuk-body govuk-!-margin-bottom-0" id="finish-to-send">Finish the technical review to send it</p>
		{/if}
	{/snippet}
</ReviewStep>

<style>
	.review-and-send__ready {
		color: #00703c;
	}

	.review-and-send__to-do {
		color: #7a3c1c;
	}

	/* A heavier rule above the list, as in the design, marks where the summary starts. */
	.review-and-send {
		border-top: 2px solid #0b0c0c;
	}

	/* Methods, urls and step values are written as they are in the schema, so they are set in a fixed width font. */
	.review-and-send__code {
		font-family: ui-monospace, Menlo, Consolas, monospace;
		font-size: 1rem;
		overflow-wrap: anywhere;
	}
</style>
