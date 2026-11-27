<script lang="ts">
	import ModuleMenu from '$lib/modules/ModuleMenu.svelte';
	import { basicCategories, type PaletteTool } from '$lib/modules/module-catalogue';
	import ProcessCanvas from '$lib/process-graph/ProcessCanvas.svelte';
	import { describeState } from '$lib/process-graph/describe-state';
	import type { DraftSet } from '$lib/process-graph/drafts';
	import { isErrorKind } from '$lib/schema/workflow/routes';
	import { processToGraph, stateTitle, visibleGraph } from '$lib/process-graph/process-to-graph';
	import { stateRows, targetOptions } from '$lib/process-graph/state-rows';
	import type { DeletedElements, NodePositions } from '$lib/process-graph/process-graph-types';
	import { applyStateEdit, canEndJourneyAt, endJourneyAt } from '$lib/schema/workflow/edit-journey';
	import { setStart } from '$lib/schema/workflow/edit-process';
	import { reachableInOrder } from '$lib/schema/workflow/journey-order';
	import { canMoveEarlier, canMoveLater, moveEarlier, moveLater } from '$lib/schema/workflow/move-state';
	import { deleteFromJourney } from '$lib/schema/workflow/remove-state';
	import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
	import StateList from '$lib/process-graph/StateList.svelte';
	import StateDetails from '$lib/service-editor/components/StateDetails.svelte';
	
	interface Props {
		process: WorkingProcess;
		showErrorRoutes: boolean;
		// Where the person has dragged boxes to, and the call that records a drag. The page holds them, so
		// they last while the page is open even after another process has been shown and this one comes back.
		positions: NodePositions;
		onMoveNodes: (moved: NodePositions) => void;
		// How many times the graph has been arranged again, and the call that arranges it again.
		layoutRound: number;
		onRearrange: () => void;
		// The shapes placed from the palette that are not in the process yet, and the call that records a change
		// to them. The page holds them for the same reason as the positions.
		drafts: DraftSet;
		onChangeDrafts: (drafts: DraftSet) => void;
		// Called with the whole process after one of its states is changed, so the page can keep the new copy.
		onChangeProcess: (process: WorkingProcess) => void;
		// Called with the id of the process an invoke box runs, when the box is clicked.
		onOpenProcess: (processId: string) => void;
	}

	let {
		process,
		showErrorRoutes,
		positions,
		onMoveNodes,
		layoutRound,
		onRearrange,
		drafts,
		onChangeDrafts,
		onChangeProcess,
		onOpenProcess
	}: Props = $props();

	// The service editor offers only the basic shapes from the module menu for now: an input, a message, a decision, a
	// start and an end. The value of an input or a message is the kind of state it adds.
	const paletteTools: PaletteTool[] = [
		{ module: 'input', value: 'input', shape: 'step' },
		{ module: 'output', value: 'output', shape: 'step' },
		{ module: 'decision', value: 'condition', shape: 'condition' },
		{ module: 'start', value: 'start', shape: 'start' },
		{ module: 'end', value: 'end', shape: 'end' }
	];

	// The graph is built once here and shared, so the canvas and the list always show the same titles and
	// numbers.
	const graph = $derived(processToGraph(process));
	// What is shown with the error routes on or off. The list and the details use it, so they never offer
	// a step that is not on the graph.
	const shown = $derived(visibleGraph(graph, { showErrorRoutes }));

	// Every state a route could lead to, named for the lists of choices in the edit form. It uses the whole graph
	// and not only what is shown, because a route can lead to a state that is hidden with the error routes.
	const targets = $derived(targetOptions(graph.nodes));

	// Every state that can be reached from the start by some route, error routes included. A state that is not
	// here can never run, which is worth telling the person after a change leaves one behind.
	const reachable = $derived(new Set(reachableInOrder(process)));

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

	// The state highlighted on the graph and in the list, and whether its edit form is open. They are held
	// together so choosing a different state always closes a form that was left open, and so a step that has just
	// been added can open straight into its form, ready for its question and title to be typed. The page shows this component
	// afresh for each process, so nothing is selected when a different process is opened.
	let selection = $state<{ code: string | null; editing: boolean }>({ code: null, editing: false });
	const selectedStateId = $derived(selection.code);

	// Highlights a state, or nothing. Choosing the state that is already highlighted leaves its form as it was.
	function select(code: string | null) {
		if (code !== selection.code) selection = { code, editing: false };
	}

	// Selects a state and opens its edit form, ready for the person to type the question and title.
	function selectAndEdit(code: string) {
		selection = { code, editing: true };
	}

	// Takes states and lines out of the process, and drops the selection if the selected state went with them.
	function removeFromProcess(deleted: Pick<DeletedElements, 'stateCodes' | 'lines'>) {
		const result = deleteFromJourney(process, deleted);
		if (!result.ok) {
			messages = [result.reason];
			return;
		}
		applyChange(result.process);
		if (selectedStateId && !(selectedStateId in result.process.states)) select(null);
	}

	// Applies the edit form for a state, with the end made in the same change when the person chose that the state
	// ends the journey.
	function applyEdit(code: string, updated: WorkingState, endsJourney: boolean) {
		applyChange(applyStateEdit(process, code, updated, endsJourney));
	}

	// Ends the journey at a state, which is the End the journey here action in the edit form.
	function handleEndJourney(code: string) {
		const result = endJourneyAt(process, code);
		if (result.ok) applyChange(result.process);
		else messages = [result.reason];
	}

	// The title of a state in this process, or nothing when no state has that code. The panel uses it to
	// name each state that a route leads to.
	function titleOf(code: string): string | undefined {
		const state = process.states[code];
		return state ? stateTitle(state, code) : undefined;
	}

	// The selected state for the panel. A state that is hidden, because only an error route leads to it,
	// has no details to show until the error routes are shown again.
	const selectedState = $derived(
		selectedStateId && shown.nodes.some((node) => node.id === selectedStateId) ? process.states[selectedStateId] : undefined
	);

	// The selected state in words. While the error routes are hidden on the graph they are left out here
	// too, so the panel never points to a step that is not shown.
	const description = $derived.by(() => {
		if (!selectedStateId || !selectedState) return undefined;
		const described = describeState(selectedState, selectedStateId, titleOf);
		return { ...described, routes: described.routes.filter((route) => showErrorRoutes || !isErrorKind(route.kind)) };
	});
</script>

<div class="process-workspace">
	<ModuleMenu categories={basicCategories} tools={paletteTools} />

	<div class="process-workspace__body">
		<ProcessCanvas
			{process}
			{graph}
			{paletteTools}
			connectedStepKind="output"
			{showErrorRoutes}
			{positions}
			{layoutRound}
			{onMoveNodes}
			{drafts}
			{onChangeDrafts}
			onChangeProcess={applyChange}
			{onOpenProcess}
			bind:selectedStateId={() => selectedStateId, select}
			bind:messages
			onEditState={selectAndEdit}
			onDeleteStates={removeFromProcess}
		/>

		<aside class="process-workspace__panel" aria-label="Steps">
			<div class="process-workspace__list">
				<StateList rows={stateRows(shown.nodes)} bind:selectedStateId={() => selectedStateId, select} />
			</div>

			{#if selectedStateId && selectedState && description}
				{@const code = selectedStateId}
				<div class="process-workspace__details">
					<!-- Shown afresh for each state, so an open edit form never carries over to another state. -->
					{#key selectedStateId}
						<StateDetails
							title={titleOf(code) ?? code}
							{description}
							currentState={selectedState}
							{targets}
							unreachable={!reachable.has(code)}
							canMoveUp={canMoveEarlier(process, code)}
							canMoveDown={canMoveLater(process, code)}
							onMove={(direction) => {
								// The graph is arranged again, so the boxes follow the new order of the list.
								applyChange((direction === 'up' ? moveEarlier : moveLater)(process, code));
								onRearrange();
							}}
							isStart={process.start === code}
							canEnd={canEndJourneyAt(process, code)}
							onSetStart={() => applyChange(setStart(process, code))}
							onEndJourney={() => handleEndJourney(code)}
							onRemove={() => removeFromProcess({ stateCodes: [code], lines: [] })}
							onApply={(updated: WorkingState, endsJourney: boolean) => applyEdit(code, updated, endsJourney)}
							onSelectState={(stateId) => {
								// A route to a state that does not exist has nothing to show.
								if (process.states[stateId]) select(stateId);
							}}
							{onOpenProcess}
							onClose={() => select(null)}
							editing={selection.editing && selection.code === code}
							onEditingChange={(editing) => (selection = { code, editing })}
						/>
					{/key}
				</div>
			{/if}
		</aside>
	</div>
</div>

<style>
	/* The module menu runs across the top, over the canvas and the panel, which sit side by side below it. */
	.process-workspace {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-height: 0;
	}

	.process-workspace__body {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	/* The list of states keeps the space it needs and scrolls on its own. When a state is selected its
		details take up to half of the panel below it and scroll on their own too, so the highlighted row
		stays in view. */
	.process-workspace__panel {
		display: flex;
		flex-direction: column;
		flex: 0 0 400px;
		min-width: 0;
		min-height: 0;
		background-color: #ffffff;
		border-left: 1px solid #b1b4b6;
	}

	.process-workspace__list {
		flex: 1 1 0;
		min-height: 0;
		overflow-y: auto;
	}

	.process-workspace__details {
		flex: 0 1 55%;
		min-height: 0;
		overflow-y: auto;
		border-top: 1px solid #b1b4b6;
	}

	@media (max-width: 900px) {
		.process-workspace__body {
			flex-direction: column;
		}

		.process-workspace__panel {
			flex-basis: auto;
			border-left: 0;
			border-top: 1px solid #b1b4b6;
		}
	}
</style>
