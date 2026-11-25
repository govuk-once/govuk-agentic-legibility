<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import SaveDraftButton from '$lib/form-editor/components/SaveDraftButton.svelte';
	import { ownerReviewProgress } from '$lib/form-editor/owner-review-progress.svelte';
	import { saveDraftAsItIs } from '$lib/form-editor/review-draft';
	import { ownerReviewSteps } from '$lib/form-editor/review-steps';
	import { isTechReviewFinished } from '$lib/form-editor/tech-review-summary';
	import { ownerDetailsOf, ownerDetailsProblems } from '$lib/schema/workflow/owner-details';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const owner = $derived(ownerDetailsOf(data.workflow.manifest));
	const hasOwner = $derived(ownerDetailsProblems(owner).length === 0);

	// What must be done before the form can be published. Each item turns green when its part of the review is done, and
	// the owner does not tick them. The validation checks have no real results yet, so they are clear unless the example
	// problems are shown.
	const checklist = $derived([
		{ label: 'Owner details added', done: hasOwner },
		{ label: 'Technical review complete', done: isTechReviewFinished(data.workflow) },
		{ label: 'Validation checks cleared', done: !ownerReviewProgress.showExampleProblems },
		{ label: 'I have read the citizen journey', done: data.draft.reviewProgress.journeyRead }
	]);
	const ready = $derived(checklist.every((item) => item.done));
</script>

<svelte:head>
	<title>Sign off: Owner review | Service Studio</title>
</svelte:head>

<ReviewStep
	steps={ownerReviewSteps(['complete', 'complete', 'current'])}
	heading="Sign off"
	hint="Confirm everything is in place. Publishing makes this form live and tells the department that you accept it."
>
	{#snippet status()}
		<p class="govuk-body govuk-!-font-weight-bold sign-off__status" class:sign-off__status--ready={ready}>
			{ready ? 'Ready to sign off' : 'Not ready to sign off'}
		</p>
	{/snippet}

	<div class="sign-off__owner">
		{#if hasOwner}
			<h2 class="govuk-heading-s govuk-!-margin-bottom-1">{owner.firstName} {owner.lastName}</h2>
			<p class="govuk-body govuk-!-margin-bottom-1 sign-off__muted">{owner.department}</p>
			<p class="govuk-body govuk-!-margin-bottom-0 sign-off__muted">{owner.email}</p>
		{:else}
			<p class="govuk-body govuk-!-margin-bottom-0">
				No owner has been added yet. <a class="govuk-link" href={resolve('/owner-review/form')}>Add the owner details</a>
			</p>
		{/if}
	</div>

	<h2 class="govuk-heading-s govuk-!-margin-top-6 govuk-!-margin-bottom-1">Before you sign off</h2>
	<ul class="govuk-list govuk-!-margin-bottom-0">
		{#each checklist as item (item.label)}
			<li class="sign-off__item">
				<span class="sign-off__mark" class:sign-off__mark--done={item.done} aria-hidden="true">
					{#if item.done}
						<svg width="12" height="12" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
							<path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="#ffffff" stroke-width="2.4" />
						</svg>
					{/if}
				</span>
				<span class="govuk-visually-hidden">{item.done ? 'Done:' : 'Not done:'}</span>
				{item.label}
			</li>
		{/each}
	</ul>

	{#snippet actions()}
		<a class="govuk-link" href={resolve('/owner-review/form/review')}>Back</a>
		<SaveDraftButton onSave={() => saveDraftAsItIs(data.draft, 'Owner review')} />
		<!-- Publishing will send the form to the workflow server. For now it only shows what happens after. -->
		<button
			class="govuk-button govuk-!-margin-bottom-0"
			type="button"
			disabled={!ready}
			onclick={() => goto(resolve('/owner-review/form/published'))}
		>
			Publish
		</button>
	{/snippet}
</ReviewStep>

<style>
	.sign-off__status {
		color: #d4351c;
	}

	.sign-off__status--ready {
		color: #00703c;
	}

	.sign-off__owner {
		padding-top: 15px;
		border-top: 2px solid #0b0c0c;
	}

	.sign-off__muted {
		color: #505a5f;
	}

	.sign-off__item {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 0;
		padding: 10px 0;
		border-bottom: 1px solid #b1b4b6;
	}

	/* A round mark before each item: green with a tick when it is done, and an empty grey ring until then. */
	.sign-off__mark {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		box-sizing: border-box;
		width: 22px;
		height: 22px;
		border: 2px solid #b1b4b6;
		border-radius: 50%;
	}

	.sign-off__mark--done {
		background-color: #00703c;
		border-color: #00703c;
	}
</style>
