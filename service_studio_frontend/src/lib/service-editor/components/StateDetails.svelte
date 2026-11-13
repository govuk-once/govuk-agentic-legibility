<script lang="ts">
	import type { StateDescription } from '$lib/process-graph/describe-state';
	import type { TargetOption } from '$lib/process-graph/state-rows';
	import type { WorkingState } from '$lib/schema/workflow/working-process';
	import StateFacts from '$lib/process-graph/StateFacts.svelte';
	import StateEditor from './StateEditor.svelte';

	interface Props {
		title: string;
		description: StateDescription;
		// The state itself, which the edit form starts from.
		currentState: WorkingState;
		// Every state that a route could lead to, named for a list of choices in the edit form.
		targets: TargetOption[];
		// True when no route leads to this state from the start, so it can never run.
		unreachable: boolean;
		// Called with the changed state when an edit is applied, and whether the person chose to end the journey at it.
		onApply: (updated: WorkingState, endsJourney: boolean) => void;
		// Called with the id of a state when one of its routes is chosen, so the panel can show that state next.
		onSelectState: (stateId: string) => void;
		// Whether the step can swap places with the step before it or after it. A button is only shown for a move
		// that will work.
		canMoveUp: boolean;
		canMoveDown: boolean;
		// Called with the direction when a move button is chosen.
		onMove: (direction: 'up' | 'down') => void;
		// Whether the state is the start of the process, and whether it can end the journey. The edit form
		// only offers each of these actions when it would do something.
		isStart: boolean;
		canEnd: boolean;
		// Called when the person chooses to make the state the start, end the journey at it, or remove it.
		onSetStart: () => void;
		onEndJourney: () => void;
		onRemove: () => void;
		// Called with the id of the process an invoke state runs, when its open button is chosen.
		onOpenProcess: (processId: string) => void;
		onClose: () => void;
		// Whether the edit form is open in place of the details, and the call that opens or closes it. The workspace
		// holds this, so a step that has just been added can open straight into its form.
		editing: boolean;
		onEditingChange: (editing: boolean) => void;
	}

	let {
		title,
		description,
		currentState,
		targets,
		unreachable,
		onApply,
		onSelectState,
		canMoveUp,
		canMoveDown,
		onMove,
		isStart,
		canEnd,
		onSetStart,
		onEndJourney,
		onRemove,
		onOpenProcess,
		onClose,
		editing,
		onEditingChange
	}: Props = $props();
</script>

{#if editing}
	<div class="state-details__editing">
		<h2 class="govuk-heading-s state-details__editing-title">{title}</h2>
		<StateEditor
				{currentState}
				stateCode={description.code}
				{targets}
				{onApply}
				{isStart}
				{canEnd}
				{onSetStart}
				{onEndJourney}
				{onRemove}
				onClose={() => onEditingChange(false)}
			/>
	</div>
{:else}
	<div class="state-details">
		<div class="state-details__header">
			<h2 class="govuk-heading-s govuk-!-margin-bottom-0">{title}</h2>
			<div class="state-details__actions">
				<button type="button" class="govuk-link govuk-body state-details__link" onclick={() => onEditingChange(true)}>
					Edit
				</button>
				<button type="button" class="govuk-link govuk-body state-details__link" onclick={onClose}>Close</button>
			</div>
		</div>

		<StateFacts {title} {description} {unreachable} {onSelectState} {onOpenProcess}>
			{#if canMoveUp || canMoveDown}
				<!-- Moving a step swaps it with its neighbour in the journey, so its number changes with it. -->
				<div class="govuk-button-group">
					{#if canMoveUp}
						<button type="button" class="govuk-button govuk-button--secondary" onclick={() => onMove('up')}>Move up</button>
					{/if}
					{#if canMoveDown}
						<button type="button" class="govuk-button govuk-button--secondary" onclick={() => onMove('down')}>Move down</button>
					{/if}
				</div>
			{/if}
		</StateFacts>
	</div>
{/if}

<style>
	.state-details {
		padding: 15px;
	}

	.state-details__actions {
		display: flex;
		gap: 15px;
	}

	.state-details__editing-title {
		margin: 0;
		padding: 15px 15px 0;
	}

	.state-details__header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 15px;
	}

	/* A button that looks like a link. It is a button because it acts on the page and does not go to a new one. */
	.state-details__link {
		padding: 0;
		background: none;
		border: 0;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
</style>
