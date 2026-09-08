<script lang="ts">
	import StepReorderButtons from './StepReorderButtons.svelte';

	interface Props {
		stepId: string;
		number: number;
		title: string;
		description: string;
		tagLabel: string;
		/* Provides the colour name expected by the GOV.UK tag modifier so the supplied status receives the correct treatment. */
		tagColour: string;
		canMoveUp: boolean;
		canMoveDown: boolean;
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
		canMoveUp,
		canMoveDown,
		onEdit,
		onRemove,
		onMoveUp,
		onMoveDown
	}: Props = $props();

	// Confirming locally, rather than removing immediately on the first click, guards against an accidental click on
	// the remove icon losing a step.
	let confirmingRemoval = $state(false);
</script>

<div class="step-card" role="group" aria-label="Step {number}: {title}">
	<StepReorderButtons
		label="step {number}: {title}"
		{canMoveUp}
		{canMoveDown}
		onMoveUp={() => onMoveUp(stepId)}
		onMoveDown={() => onMoveDown(stepId)}
	/>
	<span class="step-card__number">{number}</span>
	<div class="step-card__summary">
		<h3 class="govuk-heading-s govuk-!-margin-bottom-1">{title}</h3>
		<p class="govuk-body govuk-!-margin-bottom-0">{description}</p>
	</div>
	<!-- Status uses the supplied GOV.UK colour modifier rather than local tag styling. -->
	<strong class="govuk-tag govuk-tag--{tagColour} step-card__tag">{tagLabel}</strong>

	{#if confirmingRemoval}
		<!-- An inline confirmation, rather than a browser dialog, keeps the interaction in the same GOV.UK styled surface. -->
		<span class="step-card__confirm">
			Remove this step?
			<button type="button" class="govuk-link step-card__confirm-remove" onclick={() => onRemove(stepId)}>
				Remove step
			</button>
			<button type="button" class="govuk-link" onclick={() => (confirmingRemoval = false)}>Keep step</button>
		</span>
	{:else}
		<button type="button" class="govuk-link step-card__edit" onclick={() => onEdit(stepId)}>Edit</button>
		<button
			type="button"
			class="step-card__remove"
			aria-label="Remove step {number}: {title}"
			onclick={() => (confirmingRemoval = true)}
		>
			<svg width="14" height="14" viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
				<path d="M2 2 L12 12 M12 2 L2 12" fill="none" stroke="#505a5f" stroke-width="1.6" />
			</svg>
		</button>
	{/if}
</div>

<style>
	.step-card {
		display: flex;
		align-items: center;
		gap: 15px;
		padding: 15px 20px;
		background-color: #ffffff;
		border: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.step-card__number {
		flex-shrink: 0;
		width: 20px;
		font-size: 1rem;
		font-weight: 700;
		color: #505a5f;
	}

	.step-card__summary {
		display: flex;
		flex-direction: column;
		flex-grow: 1;
		gap: 3px;
	}

	.step-card__tag {
		flex-shrink: 0;
	}

	.step-card button.govuk-link {
		flex-shrink: 0;
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		font-size: 1rem;
		cursor: pointer;
	}

	.step-card__remove {
		flex-shrink: 0;
		display: flex;
		background: none;
		border: 0;
		padding: 0;
		cursor: pointer;
	}

	.step-card__confirm {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 1rem;
		color: #0b0c0c;
	}

	.step-card__confirm-remove {
		color: #d4351c;
	}

	@media (max-width: 640px) {
		.step-card {
			align-items: flex-start;
			flex-wrap: wrap;
			padding: 15px;
		}

		.step-card__summary {
			min-width: 200px;
		}

		.step-card__confirm {
			flex-wrap: wrap;
		}
	}
</style>
