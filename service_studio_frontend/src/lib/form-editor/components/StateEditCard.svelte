<script lang="ts">
	import { untrack } from 'svelte';
	import StateContext from '$lib/components/StateContext.svelte';
	import type { ContextItem } from '$lib/components/context';
	import StateReorderButtons from '$lib/process-graph/StateReorderButtons.svelte';
	import type { TargetOption } from '$lib/process-graph/state-rows';
	import {
		descriptionOf,
		endsTheJourney,
		hintKey,
		noteOf,
		nothingYet,
		textOf,
		withNextChoice,
		withNote,
		withText,
		withTitleAndDescription
	} from '$lib/schema/workflow/edit-state';
	import type { WorkingState } from '$lib/schema/workflow/working-process';
	import { answerKindLabels, stateLabels } from '../state-labels';

	interface Props {
		// The question or message as it is now. The card starts from it and only changes a copy.
		currentState: Extract<WorkingState, { state_type: 'input' | 'output' }>;
		// The number and the title the step has on the graph and in the list, and how many steps there are.
		number: number;
		title: string;
		totalSteps: number;
		// Every other state this step could continue to, named for the list of choices.
		targets: TargetOption[];
		// Whether there is a step before or after this one in the list to open in its place.
		canOpenPrevious: boolean;
		canOpenNext: boolean;
		onOpenPrevious: () => void;
		onOpenNext: () => void;
		// Context added for the agent on this step. It is held by the page and changed straight away when added or
		// removed, not by Apply changes, because it is not part of the step.
		contextItems: ContextItem[];
		onContextChange: (items: ContextItem[]) => void;
		// Called with the changed state when the person applies. The second value is true when they chose that the
		// step ends the journey, which needs a new end that only the owner of the process can add.
		onApply: (updated: WorkingState, endsJourney: boolean) => void;
		onCancel: () => void;
		// The actions that change the shape of the journey are drawn on every card. A page that cannot do one yet
		// gives no call for it, and choosing it does nothing.
		onSetStart?: () => void;
		onEndJourney?: () => void;
		onRemove?: () => void;
	}

	let {
		currentState,
		number,
		title,
		totalSteps,
		targets,
		canOpenPrevious,
		canOpenNext,
		onOpenPrevious,
		onOpenNext,
		contextItems,
		onContextChange,
		onApply,
		onCancel,
		onSetStart,
		onEndJourney,
		onRemove
	}: Props = $props();

	// Makes the id of each field unique, so the labels stay correct if two cards are ever on the page.
	const fieldId = $props.id();

	// A question has a hint and an answer type. A message has neither.
	const isQuestion = $derived(currentState.state_type === 'input');
	const wordsLabel = $derived(stateLabels[currentState.state_type]);

	// What the person is typing. It is held here, and not in the form being edited, until they choose Apply changes.
	// The card is shown afresh for each step, so it only needs the values the step had when it opened.
	let draftTitle = $state(untrack(() => currentState.name ?? ''));
	let draftWords = $state(untrack(() => textOf(currentState)));
	let draftDescription = $state(untrack(() => descriptionOf(currentState)));
	let draftHint = $state(untrack(() => noteOf(currentState, hintKey)));
	let draftNext = $state(untrack(() => currentState.next ?? nothingYet));

	/**
	 * Builds the changed step from what was typed and hands it over. The hint is only put on a question. Closing
	 * the card is left to the page, because the page holds which step is open.
	 */
	function applyChanges() {
		const described = withTitleAndDescription(withText(currentState, draftWords), draftTitle, draftDescription);
		const hinted = isQuestion ? withNote(described, hintKey, draftHint) : described;
		onApply(withNextChoice(hinted, draftNext), draftNext === endsTheJourney);
	}
</script>

<div class="state-edit-card" role="group" aria-label="Step {number}: {title}, editing">
	<!-- The header repeats the number and title of the step, so the open form stays tied to its place in the journey. -->
	<div class="state-edit-card__header">
		<StateReorderButtons
			label="step {number}: {title}"
			groupLabel="Move between steps"
			upLabel="Edit the previous step"
			downLabel="Edit the next step"
			canMoveUp={canOpenPrevious}
			canMoveDown={canOpenNext}
			onMoveUp={onOpenPrevious}
			onMoveDown={onOpenNext}
		/>
		<span class="govuk-body-s govuk-!-font-weight-bold govuk-!-margin-bottom-0 state-edit-card__number">{number}</span>
		<div class="state-edit-card__summary">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-0">{title}</h3>
			<p class="govuk-body-s govuk-!-margin-bottom-0 state-edit-card__status">
				Editing · step {number} of {totalSteps}
			</p>
		</div>
	</div>

	<form
		class="state-edit-card__form"
		onsubmit={(event) => {
			event.preventDefault();
			applyChanges();
		}}
	>
		<div class="govuk-form-group state-edit-card__form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-title">Title</label>
			<input class="govuk-input" id="{fieldId}-title" name="title" type="text" bind:value={draftTitle} />
		</div>

		<div class="govuk-form-group state-edit-card__form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-words">{wordsLabel}</label>
			<textarea
				class="govuk-textarea govuk-!-margin-bottom-0"
				id="{fieldId}-words"
				name="words"
				rows="3"
				required
				bind:value={draftWords}
			></textarea>
		</div>

		<div class="govuk-form-group state-edit-card__form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-description">Description</label>
			<div id="{fieldId}-description-hint" class="govuk-hint govuk-!-margin-bottom-1">Not citizen facing</div>
			<textarea
				class="govuk-textarea govuk-!-margin-bottom-0"
				id="{fieldId}-description"
				name="description"
				rows="2"
				aria-describedby="{fieldId}-description-hint"
				bind:value={draftDescription}
			></textarea>
		</div>

		{#if isQuestion}
			<div class="govuk-form-group state-edit-card__form-group">
				<label class="govuk-label govuk-label--s" for="{fieldId}-hint">Hint</label>
				<textarea
					class="govuk-textarea govuk-!-margin-bottom-0"
					id="{fieldId}-hint"
					name="hint"
					rows="2"
					bind:value={draftHint}
				></textarea>
			</div>
		{/if}

		<!-- Sits before the route, straight after the step's own details. -->
		<StateContext items={contextItems} onChange={onContextChange} />

		<div class="govuk-form-group state-edit-card__form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-continues-to">Continues to</label>
			<select class="govuk-select" id="{fieldId}-continues-to" name="continues-to" bind:value={draftNext}>
				<option value={nothingYet}>Nothing yet</option>
				<option value={endsTheJourney}>Ends the journey</option>
				{#each targets as target (target.stateId)}
					<option value={target.stateId}>{target.label}</option>
				{/each}
			</select>
		</div>

		{#if currentState.state_type === 'input'}
			<!-- The kind of answer is shown for reference. It is not changed here. -->
			<p class="govuk-body-s govuk-!-margin-bottom-0 state-edit-card__answer-type">
				Answer type: {answerKindLabels[currentState.schema.kind]}
			</p>
		{/if}

		<!-- Moving the start of the journey, or ending it at this step, changes the shape of the whole journey rather
			than this one step, so these sit apart from the fields above them. -->
		<div class="state-edit-card__journey-actions">
			<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={() => onSetStart?.()}>
				Set as start step
			</button>
			<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={() => onEndJourney?.()}>
				End the journey here
			</button>
		</div>

		<div class="state-edit-card__actions">
			<button class="govuk-button state-edit-card__apply" type="submit">Apply changes</button>
			<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={onCancel}>Cancel</button>
			<button
				type="button"
				class="govuk-link govuk-body-s govuk-!-margin-bottom-0 state-edit-card__remove"
				onclick={() => onRemove?.()}
			>
				Remove step
			</button>
		</div>
	</form>
</div>

<style>
	.state-edit-card {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-height: 0;
		background-color: #ffffff;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.state-edit-card__header {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 18px 16px 14px;
		border-bottom: 1px solid #b1b4b6;
	}

	.state-edit-card__number {
		flex-shrink: 0;
		padding-top: 2px;
		color: #505a5f;
	}

	.state-edit-card__summary {
		display: flex;
		flex-direction: column;
		gap: 2px;
		/* Without this, a flex item's automatic minimum size lets its content force this column, and the
			panel around it, wider than it should be instead of wrapping within it. */
		min-width: 0;
	}

	.state-edit-card__status,
	.state-edit-card__answer-type {
		color: #505a5f;
	}

	.state-edit-card__form {
		flex: 1 1 auto;
		min-width: 0;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 15px;
		padding: 16px;
	}

	.state-edit-card__form-group {
		min-width: 0;
		margin-bottom: 0;
	}

	/* .govuk-select has no width rule of its own the way .govuk-input does, so left alone it sizes to its
		longest option instead of filling the field the way every other control in this form does. */
	.state-edit-card__form-group .govuk-select {
		width: 100%;
	}

	.state-edit-card__journey-actions {
		display: flex;
		align-items: center;
		gap: 20px;
		padding-top: 15px;
		border-top: 1px solid #b1b4b6;
	}

	.state-edit-card__actions {
		display: flex;
		align-items: center;
		gap: 20px;
	}

	.state-edit-card__apply {
		margin-bottom: 0;
	}

	.state-edit-card__remove {
		color: #d4351c;
	}

	@media (max-width: 640px) {
		.state-edit-card__header,
		.state-edit-card__actions {
			align-items: flex-start;
			flex-wrap: wrap;
		}
	}
</style>
