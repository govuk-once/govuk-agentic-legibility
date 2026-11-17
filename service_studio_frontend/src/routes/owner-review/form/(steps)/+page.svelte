<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { tick } from 'svelte';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import { ownerReviewSteps } from '$lib/form-editor/owner-review-steps';
	import { saveFormForReview } from '$lib/form-editor/review-store';
	import {
		agentNotesLimit,
		ownerDetailsOf,
		ownerDetailsProblems,
		withOwnerDetails,
		type OwnerDetails,
		type OwnerDetailsField,
		type OwnerDetailsProblem
	} from '$lib/schema/workflow/owner-details';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// The details the form already holds, which fill the fields when the page opens. What is typed is read from the
	// fields when the person continues, and only written to the form when it passes its check.
	const saved = $derived(ownerDetailsOf(data.workflow.manifest));

	// Whether the form already holds an owner, which the status under the heading reports.
	const hasOwner = $derived(ownerDetailsProblems(saved).length === 0);

	// How long the notes for the agent are, for the count under them. It starts from the saved notes and follows
	// what is typed.
	let notesLength = $derived(saved.agentNotes.length);

	// The problems found when the person last tried to continue. They are only shown after that, so an empty field is
	// not marked as wrong before anything has been typed.
	let problems = $state<OwnerDetailsProblem[]>([]);
	const problemFor = (field: OwnerDetailsField) => problems.find((problem) => problem.field === field)?.message;
	const notesProblem = $derived(problemFor('agentNotes'));

	let errorSummary = $state<HTMLDivElement>();

	// The id of each field, so the error summary can link to it.
	const fieldIds: Record<OwnerDetailsField, string> = {
		firstName: 'owner-first-name',
		lastName: 'owner-last-name',
		department: 'owner-department',
		email: 'owner-email',
		agentPage: 'agent-page',
		agentNotes: 'agent-notes'
	};

	/**
	 * Checks the details and, when they pass, writes them into the form held in the browser tab and goes on to the
	 * review. When they do not, the problems are listed at the top and the list is focused, as GOV.UK error summaries are.
	 */
	async function continueToReview(event: SubmitEvent & { currentTarget: HTMLFormElement }) {
		event.preventDefault();
		const fields = new FormData(event.currentTarget);
		const read = (field: OwnerDetailsField) => String(fields.get(field) ?? '');
		const details: OwnerDetails = {
			firstName: read('firstName'),
			lastName: read('lastName'),
			department: read('department'),
			email: read('email'),
			agentPage: read('agentPage'),
			agentNotes: read('agentNotes')
		};
		problems = ownerDetailsProblems(details);
		if (problems.length > 0) {
			await tick();
			errorSummary?.focus();
			return;
		}
		saveFormForReview({ ...data.workflow, manifest: withOwnerDetails(data.workflow.manifest, details) });
		// The layout opened the form before the details were added, so it is opened again to pick them up.
		await goto(resolve('/owner-review/form/review'), { invalidateAll: true });
	}
</script>

<svelte:head>
	<title>{problems.length > 0 ? 'Error: ' : ''}Details: Owner review | Service Studio</title>
</svelte:head>

{#snippet textField(
	field: OwnerDetailsField,
	label: string,
	type: 'text' | 'email' | 'url',
	autocomplete: AutoFill,
	hint?: string
)}
	{@const problem = problemFor(field)}
	{@const describedBy = [hint && `${fieldIds[field]}-hint`, problem && `${fieldIds[field]}-error`].filter(Boolean).join(' ')}
	<div class="govuk-form-group" class:govuk-form-group--error={problem}>
		<label class="govuk-label govuk-label--s" for={fieldIds[field]}>{label}</label>
		{#if hint}
			<div id="{fieldIds[field]}-hint" class="govuk-hint">{hint}</div>
		{/if}
		{#if problem}
			<p id="{fieldIds[field]}-error" class="govuk-error-message">
				<span class="govuk-visually-hidden">Error:</span>
				{problem}
			</p>
		{/if}
		<input
			class="govuk-input"
			class:govuk-input--error={problem}
			id={fieldIds[field]}
			name={field}
			{type}
			{autocomplete}
			spellcheck="false"
			aria-describedby={describedBy || undefined}
			value={saved[field]}
		/>
	</div>
{/snippet}

<ReviewStep
	steps={ownerReviewSteps(['current', 'upcoming', 'upcoming'])}
	heading="Details"
	hint="Who owns this form and what the agent should know before it is used."
>
	{#snippet status()}
		<p class="govuk-body govuk-!-font-weight-bold">{hasOwner ? 'Saved' : 'Not saved yet'}</p>
	{/snippet}

	{#if problems.length > 0}
		<div class="govuk-error-summary" bind:this={errorSummary} tabindex="-1" role="alert">
			<h2 class="govuk-error-summary__title">There is a problem</h2>
			<div class="govuk-error-summary__body">
				<ul class="govuk-list govuk-error-summary__list">
					{#each problems as problem (problem.field)}
						<li><a href="#{fieldIds[problem.field]}">{problem.message}</a></li>
					{/each}
				</ul>
			</div>
		</div>
	{/if}

	<form id="owner-details" novalidate onsubmit={continueToReview}>
		<h2 class="govuk-heading-m govuk-!-margin-bottom-2">Owner</h2>
		<p class="govuk-hint govuk-!-margin-bottom-4">
			The person accountable for this form once it is live. Only they can sign off, and they are told whenever it
			changes.
		</p>
		<!-- Two fields to a row, as the details are short and full width fields would look as if they needed more. -->
		<div class="govuk-grid-row">
			<div class="govuk-grid-column-one-half">{@render textField('firstName', 'First name', 'text', 'given-name')}</div>
			<div class="govuk-grid-column-one-half">{@render textField('lastName', 'Last name', 'text', 'family-name')}</div>
		</div>
		<div class="govuk-grid-row">
			<div class="govuk-grid-column-one-half">{@render textField('department', 'Department', 'text', 'organization', 'For example, DVLA or DWP')}</div>
			<div class="govuk-grid-column-one-half">{@render textField(
					'email',
					'Email',
					'email',
					'email',
					'A team inbox is better than a personal one'
				)}</div>
		</div>

		<div class="owner-details__agent-context govuk-!-margin-top-7">
			<h2 class="govuk-heading-m govuk-!-margin-bottom-2">
				Agent context <span class="govuk-!-font-weight-regular">(optional)</span>
			</h2>
			<p class="govuk-hint govuk-!-margin-bottom-4">
				Background the agent can use every time the form is used. Leaving it blank does not affect sign off.
			</p>
			{@render textField(
				'agentPage',
				'Page for the agent to read',
				'url',
				'off',
				'A GOV.UK page, for example https://www.gov.uk/renew-driving-licence'
			)}

			<div class="govuk-form-group govuk-!-margin-bottom-0" class:govuk-form-group--error={notesProblem}>
				<label class="govuk-label govuk-label--s" for={fieldIds.agentNotes}>Notes for the agent</label>
				<div id="agent-notes-hint" class="govuk-hint">
					For example, how to speak to people and anything the agent must never ask for
				</div>
				{#if notesProblem}
					<p id="agent-notes-error" class="govuk-error-message">
						<span class="govuk-visually-hidden">Error:</span>
						{notesProblem}
					</p>
				{/if}
				<textarea
					class="govuk-textarea govuk-!-margin-bottom-1"
					class:govuk-textarea--error={notesProblem}
					id={fieldIds.agentNotes}
					name="agentNotes"
					rows="5"
					aria-describedby="agent-notes-hint agent-notes-count{notesProblem ? ' agent-notes-error' : ''}"
					value={saved.agentNotes}
					oninput={(event) => (notesLength = event.currentTarget.value.length)}
				></textarea>
				<p id="agent-notes-count" class="govuk-body-s govuk-!-margin-bottom-0 owner-details__count" aria-live="polite">
					{notesLength.toLocaleString('en-GB')} of {agentNotesLimit.toLocaleString('en-GB')} characters
				</p>
			</div>
		</div>
	</form>

	{#snippet actions()}
		<button class="govuk-button govuk-!-margin-bottom-0" type="submit" form="owner-details">Continue to review</button>
		<a class="govuk-link" role="link" aria-disabled="true">Save for later</a>
	{/snippet}
</ReviewStep>

<style>
	/* The optional context for the agent sits in a grey panel, so it reads as apart from the owner's details. */
	.owner-details__agent-context {
		padding: 30px;
		background-color: #f3f2f1;
	}

	.owner-details__count {
		color: #505a5f;
	}
</style>
