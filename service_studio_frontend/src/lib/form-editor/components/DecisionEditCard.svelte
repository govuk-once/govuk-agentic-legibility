<script lang="ts">
	import { untrack } from 'svelte';
	import { describeCondition } from '$lib/process-graph/describe-value';
	import type { TargetOption } from '$lib/process-graph/state-rows';
	import { answerChoices, answerOfCondition, conditionForAnswer } from '$lib/schema/workflow/choice-answers';
	import { descriptionOf, withTitleAndDescription } from '$lib/schema/workflow/edit-state';
	import { isUndecidedRule } from '$lib/schema/workflow/placeholders';
	import type { WorkingState } from '$lib/schema/workflow/working-process';

	// The question a decision follows, with the number and title it has on the graph.
	type QuestionBefore = { question: Extract<WorkingState, { state_type: 'input' }>; number: number; title: string };

	interface Props {
		// The decision as it is now. The card starts from it and only changes a copy.
		currentState: Extract<WorkingState, { state_type: 'choice' }>;
		// The title the decision has in the lists of choices.
		title: string;
		// The question the decision follows. There is none when a message leads to it, or more than one step does.
		before: QuestionBefore | undefined;
		// Every other state a way on could lead to, named for the list of choices.
		targets: TargetOption[];
		// Called with the changed decision when the person applies.
		onApply: (updated: WorkingState) => void;
		onCancel: () => void;
		// Removing is drawn on every card. A page that cannot do it yet gives no call for it, and choosing it does nothing.
		onRemove?: () => void;
	}

	let { currentState, title, before, targets, onApply, onCancel, onRemove }: Props = $props();

	// Makes the id of each field unique, so the labels stay correct if two cards are ever on the page.
	const fieldId = $props.id();

	// The value in the list of answers that stands for no answer chosen yet. An answer's own value is never empty.
	const notDecided = '';

	// The answers the question offers. A question answered by typing offers none, and so does a decision that
	// follows no question.
	const choices = $derived(before ? answerChoices(before.question) : []);

	/**
	 * Tells whether the answer of a rule can be chosen from the list. It can when the question offers answers and
	 * the rule is either still to be decided or already for one of them. Any other rule is shown as it is written.
	 */
	function isPickable(index: number): boolean {
		const condition = currentState.rules[index].when;
		if (!before || choices.length === 0) return false;
		return isUndecidedRule(condition) || answerOfCondition(before.question, condition) !== undefined;
	}

	// What the person is choosing. It is held here, and not in the form being edited, until they choose Apply changes.
	// The card is shown afresh for each decision, so it only needs the values the decision had when it opened.
	let draftTitle = $state(untrack(() => currentState.name ?? ''));
	let draftAnswers = $state(
		untrack(() => currentState.rules.map((rule) => (before ? answerOfCondition(before.question, rule.when) : undefined) ?? notDecided))
	);
	let draftTargets = $state(untrack(() => currentState.rules.map((rule) => rule.next)));
	let draftDefault = $state(untrack(() => currentState.default));

	/**
	 * Builds the changed decision from what was chosen and hands it over. A rule whose answer was chosen is written
	 * for that answer. A rule left as not decided, or one that cannot be chosen here, keeps the test it had.
	 */
	function applyChanges() {
		const rules = currentState.rules.map((rule, index) => {
			const chosen = before && isPickable(index) ? conditionForAnswer(before.question, draftAnswers[index]) : undefined;
			return { when: chosen ?? rule.when, next: draftTargets[index] };
		});
		const titled = withTitleAndDescription({ ...currentState, rules, default: draftDefault }, draftTitle, descriptionOf(currentState));
		onApply(titled);
	}
</script>

<div class="decision-edit-card" role="group" aria-label="Decision: {title}, editing">
	<div class="decision-edit-card__header">
		<h3 class="govuk-heading-s govuk-!-margin-bottom-0">{title}</h3>
		<p class="govuk-body-s govuk-!-margin-bottom-0 decision-edit-card__status">
			{#if before}
				Decides on the answer to step {before.number}: {before.title}
			{:else}
				Does not follow a single question
			{/if}
		</p>
	</div>

	<form
		class="decision-edit-card__form"
		onsubmit={(event) => {
			event.preventDefault();
			applyChanges();
		}}
	>
		<div class="govuk-form-group decision-edit-card__form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-title">Title</label>
			<input class="govuk-input" id="{fieldId}-title" name="title" type="text" bind:value={draftTitle} />
		</div>

		{#each currentState.rules as rule, index (index)}
			<div class="decision-edit-card__way">
				{#if isPickable(index)}
					<div class="govuk-form-group decision-edit-card__form-group">
						<label class="govuk-label govuk-label--s" for="{fieldId}-answer-{index}">If the answer is</label>
						<select class="govuk-select" id="{fieldId}-answer-{index}" name="answer-{index}" bind:value={draftAnswers[index]}>
							<option value={notDecided}>Not decided yet</option>
							{#each choices as choice (choice.value)}
								<option value={choice.value}>{choice.label}</option>
							{/each}
						</select>
					</div>
				{:else}
					<!-- A rule that is not about one of the question's answers is shown in words and is not changed here. -->
					<p class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">
						{isUndecidedRule(rule.when) ? 'Not decided yet' : `If ${describeCondition(rule.when)}`}
					</p>
				{/if}

				<div class="govuk-form-group decision-edit-card__form-group">
					<label class="govuk-label govuk-label--s" for="{fieldId}-target-{index}">Go to</label>
					<select class="govuk-select" id="{fieldId}-target-{index}" name="target-{index}" bind:value={draftTargets[index]}>
						{#each targets as target (target.stateId)}
							<option value={target.stateId}>{target.label}</option>
						{/each}
					</select>
				</div>
			</div>
		{/each}

		<div class="decision-edit-card__way">
			<div class="govuk-form-group decision-edit-card__form-group">
				<label class="govuk-label govuk-label--s" for="{fieldId}-default">Otherwise, go to</label>
				<select class="govuk-select" id="{fieldId}-default" name="default" bind:value={draftDefault}>
					{#each targets as target (target.stateId)}
						<option value={target.stateId}>{target.label}</option>
					{/each}
				</select>
			</div>
		</div>

		<div class="decision-edit-card__actions">
			<button class="govuk-button decision-edit-card__apply" type="submit">Apply changes</button>
			<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={onCancel}>Cancel</button>
			<button
				type="button"
				class="govuk-link govuk-body-s govuk-!-margin-bottom-0 decision-edit-card__remove"
				onclick={() => onRemove?.()}
			>
				Remove decision
			</button>
		</div>
	</form>
</div>

<style>
	.decision-edit-card {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-height: 0;
		background-color: #ffffff;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.decision-edit-card__header {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 18px 16px 14px;
		border-bottom: 1px solid #b1b4b6;
	}

	.decision-edit-card__status {
		color: #505a5f;
	}

	.decision-edit-card__form {
		flex: 1 1 auto;
		min-width: 0;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 15px;
		padding: 16px;
	}

	.decision-edit-card__form-group {
		min-width: 0;
		margin-bottom: 0;
	}

	/* .govuk-select has no width rule of its own the way .govuk-input does, so left alone it sizes to its
		longest option instead of filling the field the way every other control in this form does. */
	.decision-edit-card__form-group .govuk-select {
		width: 100%;
	}

	/* Each way on is set apart from the one before it, so it is clear which answer goes with which step. */
	.decision-edit-card__way {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
		padding-top: 15px;
		border-top: 1px solid #b1b4b6;
	}

	.decision-edit-card__actions {
		display: flex;
		align-items: center;
		gap: 20px;
		padding-top: 15px;
		border-top: 1px solid #b1b4b6;
	}

	.decision-edit-card__apply {
		margin-bottom: 0;
	}

	.decision-edit-card__remove {
		color: #d4351c;
	}

	@media (max-width: 640px) {
		.decision-edit-card__actions {
			align-items: flex-start;
			flex-wrap: wrap;
		}
	}
</style>
