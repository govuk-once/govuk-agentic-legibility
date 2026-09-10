<script lang="ts">
	import RemoveStepConfirm from './RemoveStepConfirm.svelte';
	import StepReorderButtons from './StepReorderButtons.svelte';
	import type { AnswerType, JourneyStep } from '$lib/journey/types';

	interface OtherStep {
		id: string;
		number: number;
		title: string;
	}

	interface Props {
		step: JourneyStep;
		number: number;
		otherSteps: OtherStep[];
		canMoveUp: boolean;
		canMoveDown: boolean;
		onApply: (updatedStep: JourneyStep) => void;
		onCancel: (stepId: string) => void;
		onRemove: (stepId: string) => void;
		onMoveUp: (stepId: string) => void;
		onMoveDown: (stepId: string) => void;
	}

	let {
		step,
		number,
		otherSteps,
		canMoveUp,
		canMoveDown,
		onApply,
		onCancel,
		onRemove,
		onMoveUp,
		onMoveDown
	}: Props = $props();

	// The component identifier keeps label targets unique when more than one step is open for editing.
	const componentId = $props.id();

	// Held locally so typing does not touch the shared step list until Apply changes commits it. Seeded
	// empty rather than from step here, because the effect below populates the real values immediately on
	// mount, and seeding from step directly here would leave a stale copy that only matches step by
	// coincidence at declaration time rather than by being kept in sync.
	let draftTitle = $state('');
	let draftAnswerType = $state<AnswerType>('question-group');
	let draftBranchesTo = $state('');

	// Confirming locally, rather than removing on the first click, guards against an accidental click on
	// Remove step losing a step's edits.
	let confirmingRemoval = $state(false);

	/**
	 * Sets the draft back to the step's currently committed values.
	 */
	function resetDraftFromStep() {
		draftTitle = step.title;
		draftAnswerType = step.answerType;
		draftBranchesTo = step.branchesTo ?? '';
	}

	// Keeps the draft matching step whenever it changes, which is what makes opening a different step
	// start with a clean draft rather than carrying over the previous step's unsaved text.
	$effect(() => {
		resetDraftFromStep();
	});

	/**
	 * Builds the updated step from the current draft values, commits it to the shared step list, and
	 * closes the editor. Closing is left to the parent, via onApply, since selection and editing state
	 * both live there.
	 */
	function applyChanges() {
		onApply({
			...step,
			title: draftTitle,
			answerType: draftAnswerType,
			branchesTo: draftBranchesTo === '' ? null : draftBranchesTo
		});
	}
</script>

<div class="step-editor" role="group" aria-label="Step {number}: {step.title}, editing">
	<!-- The header repeats the step identity so the open form remains tied to its journey position. -->
	<div class="step-editor__header">
		<StepReorderButtons
			label="step {number}: {step.title}"
			{canMoveUp}
			{canMoveDown}
			onMoveUp={() => onMoveUp(step.id)}
			onMoveDown={() => onMoveDown(step.id)}
		/>
		<span class="step-editor__number">{number}</span>
		<div class="step-editor__summary">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-1">{step.title}</h3>
			<p class="govuk-body govuk-!-margin-bottom-0">{step.description}</p>
		</div>
		<strong class="govuk-tag govuk-tag--yellow step-editor__tag">Editing</strong>
	</div>

	<!-- Form controls use unique identifiers so labels remain correct when several editors are rendered. -->
	<div class="step-editor__form">
		<div class="govuk-form-group step-editor__form-group">
			<label class="govuk-label govuk-label--s" for="{componentId}-step-title">Step title</label>
			<input
				class="govuk-input step-editor__title-input"
				id="{componentId}-step-title"
				name="step-title"
				type="text"
				bind:value={draftTitle}
			/>
		</div>

		<div class="step-editor__select-row">
			<div class="govuk-form-group step-editor__form-group">
				<label class="govuk-label govuk-label--s" for="{componentId}-answer-type">Answer type</label>
				<select class="govuk-select" id="{componentId}-answer-type" name="answer-type" bind:value={draftAnswerType}>
					<option value="question-group">Question group</option>
					<option value="single-question">Single question</option>
					<option value="file-upload">File upload</option>
					<option value="declaration">Declaration</option>
				</select>
			</div>
			<div class="govuk-form-group step-editor__form-group">
				<label class="govuk-label govuk-label--s" for="{componentId}-branches-to">Branches to</label>
				<!-- Options are generated from the other steps currently in the journey so this list never goes
					stale when steps are added, removed or reordered. -->
				<select
					class="govuk-select"
					id="{componentId}-branches-to"
					name="branches-to"
					bind:value={draftBranchesTo}
				>
					<option value="">Default, continues to the next step</option>
					{#each otherSteps as other (other.id)}
						<option value={other.id}>Step {other.number}: {other.title}</option>
					{/each}
				</select>
			</div>
		</div>

		{#if confirmingRemoval}
			<RemoveStepConfirm onRemove={() => onRemove(step.id)} onCancel={() => (confirmingRemoval = false)} />
		{:else}
			<div class="step-editor__actions">
				<button class="govuk-button step-editor__apply" type="button" onclick={applyChanges}>
					Apply changes
				</button>
				<button type="button" class="govuk-link" onclick={() => onCancel(step.id)}>Cancel</button>
				<button type="button" class="govuk-link step-editor__remove" onclick={() => (confirmingRemoval = true)}>
					Remove step
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	.step-editor {
		background-color: #ffffff;
		border: 3px solid #1d70b8;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.step-editor__header {
		display: flex;
		align-items: center;
		gap: 15px;
		padding: 15px;
	}

	.step-editor__number {
		flex-shrink: 0;
		width: 20px;
		font-size: 1rem;
		font-weight: 700;
		color: #505a5f;
	}

	.step-editor__summary {
		display: flex;
		flex-direction: column;
		flex-grow: 1;
		gap: 3px;
	}

	.step-editor__tag {
		flex-shrink: 0;
	}

	.step-editor__form {
		display: flex;
		flex-direction: column;
		gap: 15px;
		padding: 5px 15px 20px 50px;
	}

	.step-editor__form-group {
		margin-bottom: 0;
	}

	.step-editor__title-input {
		max-width: 420px;
	}

	.step-editor__select-row {
		display: flex;
		gap: 25px;
		flex-wrap: wrap;
	}

	.step-editor__actions {
		display: flex;
		align-items: center;
		gap: 20px;
	}

	.step-editor__apply {
		margin-bottom: 0;
	}

	.step-editor__form button.govuk-link {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		cursor: pointer;
	}

	.step-editor__remove {
		color: #d4351c;
	}

	@media (max-width: 640px) {
		.step-editor__header,
		.step-editor__select-row,
		.step-editor__actions {
			align-items: flex-start;
			flex-wrap: wrap;
		}

		.step-editor__summary {
			min-width: 200px;
		}

		.step-editor__form {
			padding: 5px 15px 20px;
		}
	}
</style>
