<script lang="ts">
	import { untrack } from 'svelte';
	import RemoveStepConfirm from '$lib/components/RemoveStepConfirm.svelte';
	import StateContext from '$lib/components/StateContext.svelte';
	import type { ContextItem } from '$lib/components/context';
	import ModuleNote from '$lib/modules/ModuleNote.svelte';
	import { isInModule } from '$lib/modules/module-group';
	import { answerFormatOf, answerFormats, formatsFor, isAnswerFormatKey, withAnswerFormat } from '$lib/modules/answer-formats';
	import type { TargetOption } from '$lib/process-graph/state-rows';
	import { editableOptions, newOption, withOptions } from '$lib/schema/workflow/answer-options';
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
	import { answerKindLabels } from '$lib/form-editor/state-labels';

	interface Props {
		// The input or message as it is now. The card starts from it and only changes a copy.
		currentState: Extract<WorkingState, { state_type: 'input' | 'output' }>;
		// The number and the title the step has on the graph and in the list, and how many steps there are. The title
		// is only read out to a screen reader, because the title field below already shows it.
		number: number;
		title: string;
		totalSteps: number;
		// Every other state this step could continue to, named for the list of choices.
		targets: TargetOption[];
		// Context added for the agent on this step. It is held by the page and changed straight away when added or
		// removed, not by Apply changes, because it is not part of the step.
		contextItems: ContextItem[];
		onContextChange: (items: ContextItem[]) => void;
		// Called with the changed state when the person applies. The second value is true when they chose that the
		// step ends the journey, which needs a new end that only the owner of the process can add.
		onApply: (updated: WorkingState, endsJourney: boolean) => void;
		onCancel: () => void;
		// Makes this step the start of the journey, and ends the journey at this step. Each is only offered when the
		// page gives a call for it, which it does when the action would change something.
		onSetStart?: () => void;
		onEndJourney?: () => void;
		onRemove: () => void;
	}

	let {
		currentState,
		number,
		title,
		totalSteps,
		targets,
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

	// An input has a hint and an answer type. A message has neither. The words field is named after what it holds:
	// the question an input asks, or the message an output shows.
	const isInput = $derived(currentState.state_type === 'input');
	const wordsLabel = $derived(isInput ? 'Question' : 'Message');

	// What the person is typing. It is held here, and not in the form being edited, until they choose Apply changes.
	// The card is shown afresh for each step, so it only needs the values the step had when it opened.
	let draftTitle = $state(untrack(() => currentState.name ?? ''));
	let draftWords = $state(untrack(() => textOf(currentState)));
	let draftDescription = $state(untrack(() => descriptionOf(currentState)));
	let draftHint = $state(untrack(() => noteOf(currentState, hintKey)));
	let draftNext = $state(untrack(() => currentState.next ?? nothingYet));
	// The options of an input where the person chooses, copied so each label can be typed into. An input with no
	// options to change has none, and the options are not shown.
	let draftOptions = $state(untrack(() => editableOptions(currentState)?.map((option) => ({ ...option }))));

	// The formats the module this input came from offers for its answer, and the one chosen. No format is held as an
	// empty value, which is the first choice in the list.
	const formats = untrack(() => formatsFor(currentState));
	let draftFormat = $state(untrack(() => answerFormatOf(currentState) ?? ''));

	// Removing asks first, in place of the buttons, so one stray click does not lose a step. A step that came in with
	// a module takes the whole module with it, so the buttons say module.
	let confirmingRemoval = $state(false);
	const removeNoun = $derived(isInModule(currentState) ? 'module' : 'step');

	/**
	 * Builds the changed step from what was typed and hands it over. The hint is only put on an input. Closing
	 * the card is left to the page, because the page holds which step is open.
	 */
	function applyChanges() {
		const described = withTitleAndDescription(withText(currentState, draftWords), draftTitle, draftDescription);
		const hinted = isInput ? withNote(described, hintKey, draftHint) : described;
		const optioned = draftOptions ? withOptions(hinted, draftOptions) : hinted;
		const formatted = formats.length > 0 ? withAnswerFormat(optioned, isAnswerFormatKey(draftFormat) ? draftFormat : undefined) : optioned;
		onApply(withNextChoice(formatted, draftNext), draftNext === endsTheJourney);
	}
</script>

<div class="state-edit-card" role="group" aria-label="Step {number}: {title}, editing">
	<!-- The header says which module the step belongs to, when it came in with one, and where it is in the journey.
		The title is not repeated here, because the title field below shows it. -->
	<div class="state-edit-card__header">
		<ModuleNote {currentState} />
		<p class="govuk-body-s govuk-!-margin-bottom-0 secondary-text">Editing · step {number} of {totalSteps}</p>
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

		{#if isInput}
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

		{#if formats.length > 0}
			<div class="govuk-form-group state-edit-card__form-group">
				<label class="govuk-label govuk-label--s" for="{fieldId}-format">Answer format</label>
				<div id="{fieldId}-format-hint" class="govuk-hint govuk-!-margin-bottom-1">The answer is checked against this format</div>
				<select
					class="govuk-select"
					id="{fieldId}-format"
					name="format"
					aria-describedby="{fieldId}-format-hint"
					bind:value={draftFormat}
				>
					<option value="">None</option>
					{#each formats as format (format)}
						<option value={format}>{answerFormats[format].label}</option>
					{/each}
				</select>
			</div>
		{/if}

		{#if draftOptions}
			<!-- Each option is typed in its own field. Its value was made when it was added and is not shown, because a
				decision tests the value and it must not change while the words are edited. -->
			<fieldset class="govuk-fieldset state-edit-card__form-group">
				<legend class="govuk-fieldset__legend govuk-fieldset__legend--s">Options</legend>
				<ul class="govuk-list state-edit-card__options">
					{#each draftOptions as option, index (option.value)}
						<li class="state-edit-card__option">
							<label class="govuk-label govuk-visually-hidden" for="{fieldId}-option-{index}">Option {index + 1}</label>
							<input
								class="govuk-input"
								id="{fieldId}-option-{index}"
								name="option-{index}"
								type="text"
								required
								bind:value={option.label}
							/>
							{#if draftOptions.length > 1}
								<button
									type="button"
									class="govuk-link govuk-body-s govuk-!-margin-bottom-0 state-edit-card__remove"
									onclick={() => draftOptions?.splice(index, 1)}
								>
									Remove<span class="govuk-visually-hidden"> option {index + 1}</span>
								</button>
							{/if}
						</li>
					{/each}
				</ul>
				<button
					type="button"
					class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
					onclick={() => draftOptions?.push(newOption(draftOptions))}
				>
					+ Add option
				</button>
			</fieldset>
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
			<p class="govuk-body-s govuk-!-margin-bottom-0 secondary-text">
				Answer type: {answerKindLabels[currentState.schema.kind]}
			</p>
		{/if}

		<!-- Moving the start of the journey, or ending it at this step, changes the shape of the whole journey rather
			than this one step, so these sit apart from the fields above them. -->
		{#if onSetStart || onEndJourney}
			<div class="state-edit-card__journey-actions">
				{#if onSetStart}
					<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={onSetStart}>
						Set as start step
					</button>
				{/if}
				{#if onEndJourney}
					<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={onEndJourney}>
						End the journey here
					</button>
				{/if}
			</div>
		{/if}

		{#if confirmingRemoval}
			<RemoveStepConfirm noun={removeNoun} {onRemove} onCancel={() => (confirmingRemoval = false)} />
		{:else}
			<div class="state-edit-card__actions">
				<button class="govuk-button state-edit-card__apply" type="submit">Apply changes</button>
				<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={onCancel}>Cancel</button>
				<button
					type="button"
					class="govuk-link govuk-body-s govuk-!-margin-bottom-0 state-edit-card__remove"
					onclick={() => (confirmingRemoval = true)}
				>
					Remove {removeNoun}
				</button>
			</div>
		{/if}
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
		flex-direction: column;
		gap: 10px;
		padding: 15px;
		border-bottom: 1px solid #b1b4b6;
	}

	.state-edit-card__form {
		flex: 1 1 auto;
		min-width: 0;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 15px;
		padding: 15px;
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

	.state-edit-card__options {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-bottom: 15px;
	}

	.state-edit-card__option {
		display: flex;
		align-items: center;
		gap: 15px;
		margin-bottom: 0;
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
		.state-edit-card__actions {
			align-items: flex-start;
			flex-wrap: wrap;
		}
	}
</style>
