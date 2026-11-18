<script lang="ts">
	import type { JourneyProblem } from '$lib/schema/workflow/validate';

	/*
		What the check finds before a form is sent to owner review, shown in the side panel in place of the list of
		steps. Errors stop the form being sent. Warnings are worth finishing but do not. Choosing a problem about a
		state highlights it on the graph and keeps this list open, so the problems can be worked through one by one.
	*/

	interface Props {
		errors: JourneyProblem[];
		warnings: JourneyProblem[];
		// The words that name a state, in the same way the editor's lists of choices name it.
		nameOf: (code: string) => string;
		onSelect: (code: string) => void;
		onBack: () => void;
		// Sends the form on. It is only offered when there are no errors.
		onContinue: () => void;
	}

	let { errors, warnings, nameOf, onSelect, onBack, onContinue }: Props = $props();

	// The sentence for a problem: the name of the state it is about, then what is wrong with it.
	function sentence(problem: JourneyProblem): string {
		return problem.state ? `${nameOf(problem.state)} ${problem.message}` : problem.message;
	}
</script>

<!-- One problem in a list. A problem about a state is a link that highlights the state on the graph. -->
{#snippet problemItem(problem: JourneyProblem)}
	<li>
		{#if problem.state}
			{@const code = problem.state}
			<a
				href="#{code}"
				onclick={(event) => {
					event.preventDefault();
					onSelect(code);
				}}>{sentence(problem)}</a
			>
		{:else}
			{sentence(problem)}
		{/if}
	</li>
{/snippet}

<div class="journey-check">
	<div class="journey-check__header">
		<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0 journey-check__back" onclick={onBack}>
			Back to steps
		</button>
		<h2 class="govuk-heading-s govuk-!-margin-bottom-0">Check before owner review</h2>
	</div>

	<div class="journey-check__body">
		{#if errors.length > 0}
			<div class="govuk-error-summary govuk-!-margin-bottom-0" role="alert">
				<h3 class="govuk-error-summary__title">Fix these before sending to owner review</h3>
				<div class="govuk-error-summary__body">
					<ul class="govuk-list govuk-error-summary__list">
						{#each errors as problem, index (index)}
							{@render problemItem(problem)}
						{/each}
					</ul>
				</div>
			</div>
		{:else}
			<p class="govuk-body govuk-!-margin-bottom-0">Nothing stops this form going to owner review.</p>
		{/if}

		{#if warnings.length > 0}
			<div>
				<h3 class="govuk-heading-s govuk-!-margin-bottom-2">Placeholder text still to replace</h3>
				<p class="govuk-body govuk-!-margin-bottom-2">These do not stop the form being sent.</p>
				<ul class="govuk-list govuk-list--bullet govuk-!-margin-bottom-0">
					{#each warnings as problem, index (index)}
						{@render problemItem(problem)}
					{/each}
				</ul>
			</div>
		{/if}

		{#if errors.length === 0}
			<button class="govuk-button govuk-!-margin-bottom-0" type="button" onclick={onContinue}>Continue to owner review</button>
		{/if}
	</div>
</div>

<style>
	.journey-check {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-height: 0;
		background-color: #ffffff;
	}

	.journey-check__header {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 5px;
		padding: 18px 16px 14px;
		border-bottom: 1px solid #b1b4b6;
	}

	.journey-check__back {
		padding: 0;
		background: none;
		border: 0;
		cursor: pointer;
	}

	.journey-check__body {
		flex: 1 1 auto;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 20px;
		padding: 16px;
	}
</style>
