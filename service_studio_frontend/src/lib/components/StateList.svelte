<script lang="ts">
	import type { StateRow } from '$lib/graph/state-rows';

	interface Props {
		rows: StateRow[];
		// The id of the state that is highlighted, here and on the graph. Null when nothing is selected.
		selectedStateId: string | null;
	}

	let { rows, selectedStateId = $bindable(null) }: Props = $props();

</script>

<div class="state-list__header">
	<h2 class="govuk-heading-s govuk-!-margin-bottom-0">Steps</h2>
	<p class="govuk-body govuk-!-margin-bottom-0 state-list__hint">
		{rows.length}
		{rows.length === 1 ? 'step' : 'steps'}
	</p>
</div>

<ul class="govuk-list state-list__items">
	{#each rows as row (row.stateId)}
		<li>
			<!-- Selecting only highlights the state, here and on the graph. It never changes the state. -->
			<button
				type="button"
				class="state-list__item"
				class:state-list__item--selected={row.stateId === selectedStateId}
				aria-pressed={row.stateId === selectedStateId}
				onclick={() => (selectedStateId = row.stateId === selectedStateId ? null : row.stateId)}
			>
				<span class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0 state-list__number" aria-hidden="true">
					{row.number}
				</span>
				<span class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">{row.title}</span>
			</button>
		</li>
	{/each}
</ul>

<style>
	.state-list__header {
		display: flex;
		flex-direction: column;
		gap: 5px;
		padding: 15px;
		border-bottom: 1px solid #b1b4b6;
	}

	.state-list__hint,
	.state-list__number {
		color: #505a5f;
	}

	.state-list__items {
		margin: 0;
	}

	.state-list__item {
		display: flex;
		align-items: baseline;
		gap: 10px;
		width: 100%;
		padding: 15px;
		background-color: #ffffff;
		border: 0;
		border-bottom: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
		text-align: left;
		cursor: pointer;
	}

	.state-list__item--selected {
		background-color: #e8f1f8;
	}

	.state-list__number {
		flex-shrink: 0;
		min-width: 25px;
	}

</style>
