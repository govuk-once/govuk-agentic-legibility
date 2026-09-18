<script lang="ts">
	import RemoveStepConfirm from './RemoveStepConfirm.svelte';
	import StepReorderButtons from './StepReorderButtons.svelte';

	interface Props {
		stepId: string;
		number: number;
		title: string;
		description: string;
		tagLabel: string;
		/* Provides the colour name expected by the GOV.UK tag modifier so the supplied status receives the correct treatment. */
		tagColour: string;
		selected: boolean;
		canMoveUp: boolean;
		canMoveDown: boolean;
		onSelect: (stepId: string) => void;
		onEdit: (stepId: string) => void;
		onRemove: (stepId: string) => void;
		onMoveUp: (stepId: string) => void;
		onMoveDown: (stepId: string) => void;
	}

	let {
		stepId,
		number,
		title,
		description,
		tagLabel,
		tagColour,
		selected,
		canMoveUp,
		canMoveDown,
		onSelect,
		onEdit,
		onRemove,
		onMoveUp,
		onMoveDown
	}: Props = $props();

	// Confirming locally, rather than removing immediately on the first click, guards against an accidental click on
	// the remove icon losing a step.
	let confirmingRemoval = $state(false);
</script>

<div class:step-card--selected={selected} class="step-card" role="group" aria-label="Step {number}: {title}">
	<StepReorderButtons
		label="step {number}: {title}"
		{canMoveUp}
		{canMoveDown}
		onMoveUp={() => onMoveUp(stepId)}
		onMoveDown={() => onMoveDown(stepId)}
	/>
	<span class="govuk-body-s govuk-!-font-weight-bold govuk-!-margin-bottom-0 step-card__number" aria-hidden="true"
		>{number}</span
	>
	<!-- A plain container, not a button, so the title stays a real heading rather than being nested inside
		interactive content, which HTML does not allow. The invisible button layered over it is the actual
		click target, sized to match by the absolute positioning below. A separate control from Edit:
		activating this only highlights the step, both in this list and on the graph, it never opens the editor. -->
	<div class="step-card__select">
		<div class="step-card__summary">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-0">{title}</h3>
			<p class="govuk-body-s govuk-!-margin-bottom-0 step-card__description">{description}</p>
			<!-- Status uses the supplied GOV.UK colour modifier rather than local tag styling. -->
			<strong class="govuk-tag govuk-tag--{tagColour} step-card__tag">{tagLabel}</strong>
		</div>
		<button
			type="button"
			class="step-card__select-target"
			aria-label="Select step {number}: {title}"
			onclick={() => onSelect(stepId)}
		></button>
	</div>

	{#if confirmingRemoval}
		<RemoveStepConfirm onRemove={() => onRemove(stepId)} onCancel={() => (confirmingRemoval = false)} />
	{:else}
		<div class="step-card__actions">
			<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={() => onEdit(stepId)}>
				Edit
			</button>
			<button
				type="button"
				class="step-card__remove"
				aria-label="Remove step {number}: {title}"
				onclick={() => (confirmingRemoval = true)}
			>
				<svg width="10" height="10" viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
					<path d="M2 2 L12 12 M12 2 L2 12" fill="none" stroke="#505a5f" stroke-width="1.6" />
				</svg>
			</button>
		</div>
	{/if}
</div>

<style>
	.step-card {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 14px 16px;
		background-color: #ffffff;
		border-bottom: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.step-card--selected {
		background-color: #e8f1f8;
	}

	.step-card__number {
		flex-shrink: 0;
		padding-top: 2px;
		color: #505a5f;
	}

	.step-card__select {
		position: relative;
		flex-grow: 1;
		min-width: 0;
	}

	.step-card__select-target {
		position: absolute;
		inset: 0;
		background: none;
		border: 0;
		padding: 0;
		margin: 0;
		cursor: pointer;
	}

	.step-card__summary {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 4px;
	}

	.step-card__description {
		color: #505a5f;
	}

	.step-card__tag {
		margin: 4px 0 0;
	}

	.step-card__actions {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.step-card__remove {
		flex-shrink: 0;
		display: flex;
		background: none;
		border: 0;
		padding: 0;
		cursor: pointer;
	}
</style>
