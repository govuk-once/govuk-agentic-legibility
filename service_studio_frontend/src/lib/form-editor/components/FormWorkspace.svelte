<script lang="ts">
	import ProcessCanvas from '$lib/process-graph/ProcessCanvas.svelte';
	import StateCard from '$lib/process-graph/StateCard.svelte';
	import type { DraftSet } from '$lib/process-graph/drafts';
	import type { DeletedElements, NodePositions } from '$lib/process-graph/process-graph-types';
	import { processToGraph, visibleGraph } from '$lib/process-graph/process-to-graph';
	import { stateRows } from '$lib/process-graph/state-rows';
	import { deleteFromJourney } from '$lib/schema/workflow/remove-state';
	import type { WorkingProcess } from '$lib/schema/workflow/working-process';
	import { formPaletteTools } from '../palette-tools';
	import { formDeveloperStateTypes } from '../schema/form-states';
	import { stateLabels, stateOutlineColours, stateTagColours } from '../state-labels';

	interface Props {
		process: WorkingProcess;
		// Shows the developer states and the error routes. Off, the graph and the list hold only the form's own steps.
		showDeveloperStates: boolean;
		// Where the person has dragged boxes to, and the call that records a drag. The page holds them, so they last
		// when the developer states are shown or hidden and this component is shown afresh.
		positions: NodePositions;
		onMoveNodes: (moved: NodePositions) => void;
		// The shapes placed from the palette that are not in the process yet, and the call that records a change to
		// them. The page holds them for the same reason as the positions.
		drafts: DraftSet;
		onChangeDrafts: (drafts: DraftSet) => void;
		// Called with the whole process after it is changed, so the page can keep the new copy.
		onChangeProcess: (process: WorkingProcess) => void;
	}

	let { process, showDeveloperStates, positions, onMoveNodes, drafts, onChangeDrafts, onChangeProcess }: Props = $props();

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

	// Why the last change could not be made, in words, shown over the canvas until it is dismissed. It is empty when
	// there is nothing to say. The canvas shows it and can add to it, so the two share it.
	let messages = $state<string[]>([]);

	/**
	 * Hands a changed process to the page. Any reason left over from an earlier change that could not be made is
	 * cleared first, because it no longer describes what is on the canvas.
	 */
	function applyChange(updated: WorkingProcess) {
		messages = [];
		onChangeProcess(updated);
	}

	// Takes states and lines out of the process, and drops the selection if the selected state went with them.
	function removeFromProcess(deleted: Pick<DeletedElements, 'stateCodes' | 'lines'>) {
		const result = deleteFromJourney(process, deleted);
		if (!result.ok) {
			messages = [result.reason];
			return;
		}
		applyChange(result.process);
		if (selectedStateId && !(selectedStateId in result.process.states)) selectedStateId = null;
	}
</script>

<div class="form-workspace">
	<!-- A step that has just been added is highlighted, on the graph and in the list, so it is easy to find. -->
	<ProcessCanvas
		{process}
		{graph}
		paletteTools={formPaletteTools}
		connectedStepKind="input"
		showErrorRoutes={showDeveloperStates}
		showDeveloperSteps={showDeveloperStates}
		stepOutlineColours={stateOutlineColours}
		{positions}
		{onMoveNodes}
		{drafts}
		{onChangeDrafts}
		onChangeProcess={applyChange}
		bind:selectedStateId
		bind:messages
		onEditState={(code) => (selectedStateId = code)}
		onDeleteStates={removeFromProcess}
	/>

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
