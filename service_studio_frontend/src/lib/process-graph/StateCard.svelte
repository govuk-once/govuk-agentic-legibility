<script lang="ts">
	import RemoveStepConfirm from '$lib/components/RemoveStepConfirm.svelte';
	import StateReorderButtons from './StateReorderButtons.svelte';

	interface Props {
		stateId: string;
		number: number;
		title: string;
		// A line of words under the title. Left out when the state has none.
		description?: string;
		tagLabel: string;
		// The colour name the GOV.UK tag modifier expects, so the tag gets the right treatment for its kind of state.
		tagColour: string;
		selected: boolean;
		canMoveUp: boolean;
		canMoveDown: boolean;
		onSelect: (stateId: string) => void;
		// The edit, remove and move actions are drawn on every card, as they are in the old editor. A page that cannot
		// do one yet gives no call for it, and choosing it does nothing.
		onEdit?: (stateId: string) => void;
		onRemove?: (stateId: string) => void;
		onMoveUp?: (stateId: string) => void;
		onMoveDown?: (stateId: string) => void;
	}

	let {
		stateId,
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

<div class:state-card--selected={selected} class="state-card" role="group" aria-label="Step {number}: {title}">
	<StateReorderButtons
		label="step {number}: {title}"
		{canMoveUp}
		{canMoveDown}
		onMoveUp={() => onMoveUp?.(stateId)}
		onMoveDown={() => onMoveDown?.(stateId)}
	/>
	<span class="govuk-body-s govuk-!-font-weight-bold govuk-!-margin-bottom-0 state-card__number" aria-hidden="true"
		>{number}</span
	>
	<!-- A plain container, not a button, so the title stays a real heading rather than being nested inside
		interactive content, which HTML does not allow. The invisible button layered over it is the actual
		click target, sized to match by the absolute positioning below. A separate control from Edit:
		activating this only highlights the step, both in this list and on the graph, it never opens the editor. -->
	<div class="state-card__select">
		<div class="state-card__summary">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-0">{title}</h3>
			{#if description}
				<p class="govuk-body-s govuk-!-margin-bottom-0 state-card__description">{description}</p>
			{/if}
			<!-- Status uses the supplied GOV.UK colour modifier rather than local tag styling. -->
			<strong class="govuk-tag govuk-tag--{tagColour} state-card__tag">{tagLabel}</strong>
		</div>
		<button
			type="button"
			class="state-card__select-target"
			aria-label="Select step {number}: {title}"
			onclick={() => onSelect(stateId)}
		></button>
	</div>

	{#if confirmingRemoval}
		<RemoveStepConfirm
			noun="step"
			onRemove={() => {
				confirmingRemoval = false;
				onRemove?.(stateId);
			}}
			onCancel={() => (confirmingRemoval = false)} />
	{:else}
		<div class="state-card__actions">
			<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={() => onEdit?.(stateId)}>
				Edit
			</button>
			<button
				type="button"
				class="state-card__remove"
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
	.state-card {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 14px 16px;
		background-color: #ffffff;
		border-bottom: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.state-card--selected {
		background-color: #e8f1f8;
	}

	.state-card__number {
		flex-shrink: 0;
		padding-top: 2px;
		color: #505a5f;
	}

	.state-card__select {
		position: relative;
		flex-grow: 1;
		min-width: 0;
	}

	.state-card__select-target {
		position: absolute;
		inset: 0;
		background: none;
		border: 0;
		padding: 0;
		margin: 0;
		cursor: pointer;
	}

	.state-card__summary {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 4px;
	}

	.state-card__description {
		color: #505a5f;
	}

	.state-card__tag {
		margin: 4px 0 0;
	}

	.state-card__actions {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.state-card__remove {
		flex-shrink: 0;
		display: flex;
		background: none;
		border: 0;
		padding: 0;
		cursor: pointer;
	}
</style>
