<script lang="ts">
	import { untrack } from 'svelte';
	import RemoveStepConfirm from '$lib/components/RemoveStepConfirm.svelte';
	import type { TargetOption } from '$lib/process-graph/state-rows';
	import { descriptionOf, nothingYet, withChoiceTargets, withTitleAndDescription } from '$lib/schema/workflow/edit-state';
	import type { WorkingState } from '$lib/schema/workflow/working-process';
	import { decisionRowLabels } from '../decision-rows';

	// The question a decision follows, with the number and title it has on the graph.
	type QuestionBefore = { question: Extract<WorkingState, { state_type: 'input' }>; number: number; title: string };

	interface Props {
		// The decision as it is now. The card starts from it and only changes a copy.
		currentState: Extract<WorkingState, { state_type: 'choice' }>;
		// The title the decision has in the lists of choices.
		title: string;
		// The question the decision follows. There is none when a message leads to it, or more than one step does.
		before: QuestionBefore | undefined;
		// Every other state a way out could lead to, named for the list of choices.
		targets: TargetOption[];
		// Called with the changed decision when the person applies.
		onApply: (updated: WorkingState) => void;
		onCancel: () => void;
		onRemove: () => void;
	}

	let { currentState, title, before, targets, onApply, onCancel, onRemove }: Props = $props();

	// Makes the id of each field unique, so the labels stay correct if two cards are ever on the page.
	const fieldId = $props.id();

	// The words beside each way out of the decision, one for each rule and then one for the way taken when no rule
	// matches. They name the answer that leads that way, and cannot be changed here.
	const rowLabels = $derived(decisionRowLabels(currentState, before?.question));

	// What the person is choosing. It is held here, and not in the form being edited, until they choose Apply changes.
	// The card is shown afresh for each decision, so it only needs the values the decision had when it opened. The
	// states the ways out lead to are held in the order of the labels, so the last is the one taken when no rule matches.
	// A way out that leads nowhere yet is held as nothing yet.
	let draftTitle = $state(untrack(() => currentState.name ?? ''));
	let draftTargets = $state(
		untrack(() => [...currentState.rules.map((rule) => rule.next ?? nothingYet), currentState.default ?? nothingYet])
	);

	// Removing asks first, in place of the buttons, so one stray click does not lose a decision.
	let confirmingRemoval = $state(false);

	/**
	 * Builds the changed decision from what was chosen and hands it over. Only where each way out leads and the
	 * title are changed. The test of every rule is kept as it was.
	 */
	function applyChanges() {
		const routed = withChoiceTargets(currentState, draftTargets.slice(0, -1), draftTargets[draftTargets.length - 1]);
		onApply(withTitleAndDescription(routed, draftTitle, descriptionOf(currentState)));
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

		<!-- One row for every way out of the decision: the answer that leads that way, and the state it leads to. -->
		{#each rowLabels as label, index (index)}
			<div class="govuk-form-group decision-edit-card__form-group decision-edit-card__way">
				<p class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-1">{label}</p>
				<label class="govuk-label" for="{fieldId}-target-{index}">Go to</label>
				<select class="govuk-select" id="{fieldId}-target-{index}" name="target-{index}" bind:value={draftTargets[index]}>
					<option value={nothingYet}>Nothing yet</option>
					{#each targets as target (target.stateId)}
						<option value={target.stateId}>{target.label}</option>
					{/each}
				</select>
			</div>
		{/each}

		{#if confirmingRemoval}
			<div class="decision-edit-card__confirm">
				<RemoveStepConfirm noun="decision" {onRemove} onCancel={() => (confirmingRemoval = false)} />
			</div>
		{:else}
			<div class="decision-edit-card__actions">
				<button class="govuk-button decision-edit-card__apply" type="submit">Apply changes</button>
				<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={onCancel}>Cancel</button>
				<button
					type="button"
					class="govuk-link govuk-body-s govuk-!-margin-bottom-0 decision-edit-card__remove"
					onclick={() => (confirmingRemoval = true)}
				>
					Remove decision
				</button>
			</div>
		{/if}
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

	/* Each way out is set apart from the one before it, so it is clear which answer goes with which state. */
	.decision-edit-card__way {
		padding-top: 15px;
		border-top: 1px solid #b1b4b6;
	}

	.decision-edit-card__actions {
		display: flex;
		align-items: center;
		gap: 20px;
	}

	/* The buttons, or the question that takes their place, are set apart from the ways out above them. */
	.decision-edit-card__actions,
	.decision-edit-card__confirm {
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
