<script lang="ts">
	import NodePalette from '$lib/graph-kit/NodePalette.svelte';
	import ProcessGraph from '$lib/process-graph/ProcessGraph.svelte';
	import StateCard from '$lib/process-graph/StateCard.svelte';
	import { processToGraph, visibleGraph } from '$lib/process-graph/process-to-graph';
	import { stateRows } from '$lib/process-graph/state-rows';
	import type { WorkingProcess } from '$lib/schema/workflow/working-process';
	import { formPaletteTools } from '../palette-tools';
	import { formDeveloperStateTypes } from '../schema/form-states';
	import { stateLabels, stateTagColours } from '../state-labels';

	interface Props {
		process: WorkingProcess;
		// Shows the developer states and the error routes. Off, the graph and the list hold only the form's own steps.
		showDeveloperStates: boolean;
	}

	let { process, showDeveloperStates }: Props = $props();

	// The graph is built once here and shared, so the canvas and the list always show the same titles and numbers.
	const graph = $derived(processToGraph(process, formDeveloperStateTypes));

	// What is shown with the developer states on or off. The list uses it, so it never offers a step that is not
	// on the graph.
	const shown = $derived(
		visibleGraph(graph, { showErrorRoutes: showDeveloperStates, showDeveloperSteps: showDeveloperStates })
	);
	const rows = $derived(stateRows(shown.nodes));

	// The state highlighted on the graph and in the list. Null when nothing is selected.
	let selectedStateId = $state<string | null>(null);
</script>

<div class="form-workspace">
	<!-- The palette is drawn as it is in the other editors. Nothing can be dropped on the graph yet, because this
		page only shows the form. -->
	<NodePalette tools={formPaletteTools} />

	<div class="form-workspace__canvas">
		<ProcessGraph
			{graph}
			readOnly
			showErrorRoutes={showDeveloperStates}
			showDeveloperSteps={showDeveloperStates}
			bind:selectedStateId
		/>
	</div>

	<aside class="form-workspace__panel" aria-label="Steps">
		<div class="form-workspace__list">
			<div class="form-workspace__list-header">
				<h2 class="govuk-heading-s govuk-!-margin-bottom-0">Steps</h2>
				<p class="govuk-body-s govuk-!-margin-bottom-0 form-workspace__list-hint">
					{rows.length} steps · nothing selected
				</p>
			</div>

			{#each rows as row, index (row.stateId)}
				<StateCard
					stateId={row.stateId}
					number={row.number}
					title={row.title}
					tagLabel={stateLabels[row.stateType]}
					tagColour={stateTagColours[row.stateType]}
					selected={row.stateId === selectedStateId}
					canMoveUp={index > 0}
					canMoveDown={index < rows.length - 1}
					onSelect={(stateId) => (selectedStateId = stateId)}
				/>
			{/each}
		</div>

		<div class="form-workspace__panel-footer">
			<button class="govuk-button govuk-!-margin-bottom-0" type="button">Send to policy review</button>
		</div>
	</aside>
</div>

<style>
	.form-workspace {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	.form-workspace__canvas {
		position: relative;
		flex: 1 1 auto;
		min-width: 0;
	}

	.form-workspace__panel {
		display: flex;
		flex-direction: column;
		flex: 0 0 400px;
		/* Without this, a flex item's automatic minimum size lets its content force the panel wider than its
			flex-basis instead of scrolling within it. */
		min-width: 0;
		min-height: 0;
		background-color: #ffffff;
		border-left: 1px solid #b1b4b6;
	}

	.form-workspace__list {
		flex: 1 1 auto;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
	}

	.form-workspace__list-header {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 18px 16px 14px;
		border-bottom: 1px solid #b1b4b6;
	}

	.form-workspace__list-hint {
		color: #505a5f;
	}

	.form-workspace__panel-footer {
		padding: 16px;
	}

	/* GOV.UK's own button is full width only below its tablet breakpoint, auto width above it. This panel is much
		narrower than that breakpoint even on a wide screen, so the button is told to stay full width of it. */
	.form-workspace__panel-footer .govuk-button {
		width: 100%;
	}

	@media (max-width: 900px) {
		.form-workspace {
			flex-direction: column;
		}

		.form-workspace__panel {
			flex-basis: auto;
			border-left: 0;
			border-top: 1px solid #b1b4b6;
		}
	}
</style>
