<script lang="ts">
	import { tick } from 'svelte';
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
	import { createDrivingLicenceGraph } from '$lib/graph/driving-licence-fixture';
	import { layoutJourneyGraph } from '$lib/graph/layout';
	import type { JourneyEdge, JourneyNode } from '$lib/graph/types';

	interface Props {
		onStepSelect: (stepId: string | null) => void;
	}

	let { onStepSelect }: Props = $props();

	const nodeTypes: NodeTypes = {
		step: StepNode,
		condition: ConditionNode,
		terminal: TerminalNode
	};
	const edgeTypes: EdgeTypes = {
		branch: BranchEdge
	};
	const { fitView } = useSvelteFlow<JourneyNode, JourneyEdge>();

	let showBranching = $state(true);
	const initialGraph = createDrivingLicenceGraph(true);
	// Raw state keeps Svelte Flow arrays replaceable without wrapping library objects in deep reactive proxies.
	let nodes = $state.raw<JourneyNode[]>(layoutJourneyGraph(initialGraph.nodes, initialGraph.edges));
	let edges = $state.raw<JourneyEdge[]>(initialGraph.edges);

	/**
	 * Recreates the temporary graph and reapplies Dagre so manual node movement can be discarded.
	 */
	async function restoreLayout() {
		// Preserve the selected node because rebuilding the graph replaces every node object.
		const selectedNodeId = nodes.find((node) => node.selected)?.id;
		const graph = createDrivingLicenceGraph(showBranching);
		const graphNodes = graph.nodes.map((node) => ({
			...node,
			selected: node.id === selectedNodeId
		}));
		nodes = layoutJourneyGraph(graphNodes, graph.edges);
		edges = graph.edges;

		// Wait for Svelte to render the replacement nodes before measuring them for the fitted viewport.
		await tick();
		await fitView({ padding: 0.15, duration: 250 });
	}

	/**
	 * Reports the selected journey step so the matching editor card can be highlighted.
	 */
	const handleSelectionChange: OnSelectionChange<JourneyNode, JourneyEdge> = ({ nodes: selectedNodes }) => {
		// Use the first selection because the page can highlight only one editor card at a time.
		const selectedNode = selectedNodes.at(0);
		const stepId = selectedNode?.type === 'step' ? selectedNode.data.stepId : undefined;
		onStepSelect(stepId ?? null);
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
				onclick={() => fitView({ padding: 0.15, duration: 250 })}
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

	<!-- Svelte Flow owns pointer and keyboard interaction while fixture edges remain read only. -->
	<div class="journey-graph__canvas">
		<SvelteFlow
			bind:nodes
			bind:edges
			{nodeTypes}
			{edgeTypes}
			fitView
			fitViewOptions={{ padding: 0.15 }}
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
