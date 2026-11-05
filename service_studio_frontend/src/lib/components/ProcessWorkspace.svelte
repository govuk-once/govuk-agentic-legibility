<script lang="ts">
	import ProcessGraph from '$lib/graph/ProcessGraph.svelte';
	import { describeState } from '$lib/graph/describe-state';
	import { isErrorKind } from '$lib/schema/workflow/routes';
	import { processToGraph, stateTitle, visibleGraph } from '$lib/graph/process-to-graph';
	import { stateRows, targetOptions } from '$lib/graph/state-rows';
	import type { NodePositions } from '$lib/graph/process-graph-types';
	import { replaceState } from '$lib/schema/workflow/edit-state';
	import { reachableInOrder } from '$lib/schema/workflow/journey-order';
	import type { Process, State } from '$lib/schema/workflow/process';
	import type { WorkflowIssue } from '$lib/schema/workflow/validate';
	import StateDetails from './StateDetails.svelte';
	import StateList from './StateList.svelte';

	interface Props {
		process: Process;
		showErrorRoutes: boolean;
		// Where the person has dragged boxes to, and the call that records a drag. The page holds them, so
		// they last while the page is open even after another process has been shown and this one comes back.
		positions: NodePositions;
		onMoveNodes: (moved: NodePositions) => void;
		// Called with the whole process after one of its states is changed. It returns any problems the schema
		// found, and an empty list when the change was accepted, so the page can refuse a change that breaks it.
		onChangeProcess: (process: Process) => WorkflowIssue[];
		// Called with the id of the process an invoke box runs, when the box is clicked.
		onOpenProcess: (processId: string) => void;
	}

	let { process, showErrorRoutes, positions, onMoveNodes, onChangeProcess, onOpenProcess }: Props = $props();

	// The graph is built once here and shared, so the canvas and the list always show the same titles and
	// numbers.
	const graph = $derived(processToGraph(process));
	// What is shown with the error routes on or off. The list and the details use it, so they never offer
	// a step that is not on the graph.
	const shown = $derived(visibleGraph(graph, showErrorRoutes));

	// Every state a route could lead to, named for the lists of choices in the edit form. It uses the whole graph
	// and not only what is shown, because a route can lead to a state that is hidden with the error routes.
	const targets = $derived(targetOptions(graph.nodes));

	// Every state that can be reached from the start by some route, error routes included. A state that is not
	// here can never run, which is worth telling the person after a change leaves one behind.
	const reachable = $derived(new Set(reachableInOrder(process)));

	// The state highlighted on the graph and in the list. The page shows this component afresh for each
	// process, so the selection starts empty every time a different process is opened.
	let selectedStateId = $state<string | null>(null);

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
	<div class="process-workspace__canvas">
		<ProcessGraph {graph} {showErrorRoutes} {positions} {onMoveNodes} bind:selectedStateId {onOpenProcess} />
	</div>

	<aside class="process-workspace__panel" aria-label="Steps">
		<div class="process-workspace__list">
			<StateList rows={stateRows(shown.nodes)} bind:selectedStateId />
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
						onApply={(updated: State) => onChangeProcess(replaceState(process, code, updated))}
						onSelectState={(stateId) => {
							// A route to a state that does not exist has nothing to show.
							if (process.states[stateId]) selectedStateId = stateId;
						}}
						{onOpenProcess}
						onClose={() => (selectedStateId = null)}
					/>
				{/key}
			</div>
		{/if}
	</aside>
</div>

<style>
	.process-workspace {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	.process-workspace__canvas {
		position: relative;
		flex: 1 1 auto;
		min-width: 0;
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
		.process-workspace {
			flex-direction: column;
		}

		.process-workspace__panel {
			flex-basis: auto;
			border-left: 0;
			border-top: 1px solid #b1b4b6;
		}
	}
</style>
