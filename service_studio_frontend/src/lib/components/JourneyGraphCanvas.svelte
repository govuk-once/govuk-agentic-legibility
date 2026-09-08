<script lang="ts">
	import { tick, untrack } from 'svelte';
	import {
		SvelteFlow,
		useSvelteFlow,
		type EdgeTypes,
		type NodeTypes,
		type OnSelectionChange
	} from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';
	import ConditionNode from './graph/ConditionNode.svelte';
	import BranchEdge from './graph/BranchEdge.svelte';
	import StepNode from './graph/StepNode.svelte';
	import TerminalNode from './graph/TerminalNode.svelte';
	import { createJourneyGraph } from '$lib/graph/build-journey-graph';
	import { layoutJourneyGraph } from '$lib/graph/layout';
	import { addressChangeBranchDecoration } from '$lib/journey/steps';
	import type { JourneyEdge, JourneyNode } from '$lib/graph/types';
	import type { JourneyStep } from '$lib/journey/types';

	interface Props {
		steps: JourneyStep[];
		selectedStepId?: string | null;
	}

	let { steps, selectedStepId = $bindable(null) }: Props = $props();

	const nodeTypes: NodeTypes = {
		step: StepNode,
		condition: ConditionNode,
		terminal: TerminalNode
	};
	const edgeTypes: EdgeTypes = {
		branch: BranchEdge
	};
	const { fitView } = useSvelteFlow<JourneyNode, JourneyEdge>();
	// Generous padding, and a maxZoom below the interactive maxZoom on SvelteFlow itself below, keeps
	// every fit-to-view action starting from a comfortably zoomed out view rather than filling the canvas.
	const fitViewOptions = { padding: 0.3, maxZoom: 0.9 };

	// A plain constant, rather than reading the showBranching state below, is what the very first graph
	// build uses: at that point in component initialisation nothing could yet have changed showBranching
	// away from this value, so they are guaranteed to agree, and using the state itself is not needed.
	const DEFAULT_SHOW_BRANCHING = true;
	let showBranching = $state(DEFAULT_SHOW_BRANCHING);

	/**
	 * Builds a laid out graph from the current steps, branching toggle and selection, all in one pass, so
	 * the graph is never left in a state where nothing is selected between building its structure and
	 * applying the selection separately.
	 */
	function buildGraph(currentShowBranching: boolean, currentSelectedStepId: string | null) {
		const graph = createJourneyGraph(steps, currentShowBranching, addressChangeBranchDecoration);
		const laidOutNodes = layoutJourneyGraph(graph.nodes, graph.edges).map((node) => ({
			...node,
			selected: node.type === 'step' && node.data.stepId === currentSelectedStepId
		}));
		return { nodes: laidOutNodes, edges: graph.edges };
	}

	const initialGraph = buildGraph(DEFAULT_SHOW_BRANCHING, selectedStepId);
	// Raw state keeps Svelte Flow arrays replaceable without wrapping library objects in deep reactive
	// proxies. Building this from the current steps up front, rather than starting empty and populating
	// via an effect, matters: Svelte Flow reports its own initial, empty selection once it mounts, and if
	// nodes started empty that report would arrive and clobber a genuine starting selection before this
	// component had a chance to apply it.
	let nodes = $state.raw<JourneyNode[]>(initialGraph.nodes);
	let edges = $state.raw<JourneyEdge[]>(initialGraph.edges);

	// Rebuilds automatically whenever the step list's order or content changes, so edits made in the panel
	// always reach the graph without needing an explicit refresh action. The branching toggle and current
	// selection are read without tracking them here, since the toggle already has its own explicit
	// handler, restoreLayout, and pure selection changes are handled by the sync effect below without
	// needing a full structural rebuild.
	$effect(() => {
		const graph = buildGraph(untrack(() => showBranching), untrack(() => selectedStepId));
		nodes = graph.nodes;
		edges = graph.edges;
	});

	/**
	 * Keeps the graph's selected node matching selectedStepId, including when it changes from outside the
	 * graph such as clicking Edit in the step list. Skips the write when they already agree, so this does
	 * not fight with handleSelectionChange writing the same value back after a click inside the graph.
	 */
	$effect(() => {
		const matchesSelection = (node: JourneyNode) =>
			Boolean(node.selected) === (node.type === 'step' && node.data.stepId === selectedStepId);

		if (nodes.every(matchesSelection)) return;

		nodes = nodes.map((node) => ({ ...node, selected: matchesSelection(node) }));
	});

	/**
	 * Rebuilds the graph and moves the viewport to fit it, discarding any manual node movement. Used by
	 * the Show branching toggle and the Restore layout button.
	 */
	async function restoreLayout() {
		const graph = buildGraph(showBranching, selectedStepId);
		nodes = graph.nodes;
		edges = graph.edges;

		// Wait for Svelte to render the replacement nodes before measuring them for the fitted viewport.
		await tick();
		await fitView({ ...fitViewOptions, duration: 250 });
	}

	/**
	 * Reports the selected journey step so the matching editor card can be highlighted.
	 */
	const handleSelectionChange: OnSelectionChange<JourneyNode, JourneyEdge> = ({ nodes: selectedNodes }) => {
		// Use the first selection because the page can highlight only one editor card at a time.
		const selectedNode = selectedNodes.at(0);
		const stepId = selectedNode?.type === 'step' ? selectedNode.data.stepId : undefined;
		selectedStepId = stepId ?? null;
	};
</script>

<!-- The graph section gives its controls and viewport one accessible heading. -->
<section class="journey-graph" aria-labelledby="journey-graph-heading">
	<header class="journey-graph__header">
		<h2 id="journey-graph-heading" class="govuk-heading-m govuk-!-margin-bottom-0">Journey graph</h2>

		<!-- Controls remain outside the viewport so moving the graph cannot move the actions themselves. -->
		<div class="journey-graph__controls">
			<!-- Changing branch visibility rebuilds and lays out the appropriate graph structure. -->
			<div class="govuk-checkboxes govuk-checkboxes--small">
				<div class="govuk-checkboxes__item">
					<input
						class="govuk-checkboxes__input"
						id="show-branching"
						type="checkbox"
						bind:checked={showBranching}
						onchange={restoreLayout}
					/>
					<label class="govuk-label govuk-checkboxes__label" for="show-branching">Show branching</label>
				</div>
			</div>

			<!-- Fitting changes only the viewport while restoring also discards temporary node movement. -->
			<button
				class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
				type="button"
				onclick={() => fitView({ ...fitViewOptions, duration: 250 })}
			>
				Fit to view
			</button>
			<button
				class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
				type="button"
				onclick={restoreLayout}
			>
				Restore layout
			</button>
		</div>
	</header>

	<!-- Svelte Flow owns pointer and keyboard interaction while graph connections remain read only. -->
	<div class="journey-graph__canvas">
		<SvelteFlow
			bind:nodes
			bind:edges
			{nodeTypes}
			{edgeTypes}
			fitView
			{fitViewOptions}
			minZoom={0.25}
			maxZoom={1.5}
			nodesConnectable={false}
			edgesFocusable={false}
			preventScrolling
			zoomOnScroll
			deleteKey={null}
			onselectionchange={handleSelectionChange}
			attributionPosition="bottom-right"
			aria-label="Interactive journey graph"
		/>
	</div>
</section>

<style>
	.journey-graph {
		display: flex;
		flex-direction: column;
		flex: 1 1 500px;
		min-width: 0;
		border: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.journey-graph__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 20px;
		padding: 15px 20px;
		background-color: #f3f2f1;
		border-bottom: 1px solid #b1b4b6;
	}

	.journey-graph__controls {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		flex-wrap: wrap;
		gap: 10px;
	}

	.journey-graph__canvas {
		height: 1100px;
		background-color: #ffffff;
	}

	.journey-graph__canvas :global(.svelte-flow__node) {
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.journey-graph__canvas :global(.svelte-flow__node:focus-visible) {
		outline: 4px solid #ffdd00;
		outline-offset: 2px;
	}

	.journey-graph__canvas :global(.svelte-flow__edge-path) {
		stroke: #505a5f;
		stroke-width: 2;
	}

	.journey-graph__canvas :global(.svelte-flow__attribution) {
		font-size: 12px;
		background-color: rgb(255 255 255 / 85%);
	}

	@media (max-width: 1100px) {
		.journey-graph {
			flex-basis: auto;
			width: 100%;
		}
	}

	@media (max-width: 640px) {
		.journey-graph__header {
			align-items: flex-start;
			flex-direction: column;
			padding: 15px;
		}

		.journey-graph__controls {
			align-items: flex-start;
			justify-content: flex-start;
			width: 100%;
		}

		.journey-graph__canvas {
			height: 680px;
		}
	}
</style>
