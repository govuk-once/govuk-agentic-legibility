<script lang="ts">
	import { SvelteFlow, Background, Controls, MarkerType, MiniMap } from '@xyflow/svelte';
	import StepNode from './StepNode.svelte';
	import ConditionNode from './ConditionNode.svelte';
	import TerminalNode from './TerminalNode.svelte';
	import { layoutJourneyGraph } from './layout';
	import { visibleGraph } from './process-to-graph';
	import type { ProcessGraphElements } from './process-graph-types';

	interface Props {
		// The nodes and edges of the process, built by the component that owns it so the list of states uses the same ones.
		graph: ProcessGraphElements;
		// The state highlighted on the graph, shared with the list of states. Null when nothing is selected.
		selectedStateId?: string | null;
		// Off by default, which hides the routes taken when something goes wrong or runs late, and the
		// states that only those routes lead to.
		showErrorRoutes?: boolean;
		// Called with the id of the process an invoke box runs, when the box is clicked.
		onOpenProcess?: (processId: string) => void;
	}

	let { graph, selectedStateId = $bindable(null), showErrorRoutes = false, onOpenProcess }: Props = $props();

	// The same three node components as the original graph, so a state looks the same in either.
	const nodeTypes = { step: StepNode, condition: ConditionNode, terminal: TerminalNode };

	// Declared once so Svelte Flow receives the same object on every update. The arrow head shows the
	// direction of a route, which matters when a route loops back to an earlier state.
	const fitViewOptions = { padding: 0.15, maxZoom: 0.9 };
	const defaultEdgeOptions = { type: 'smoothstep' as const, markerEnd: { type: MarkerType.ArrowClosed } };
	const proOptions = { hideAttribution: true };

	// The graph for the chosen process, with every node given a position. It is worked out again when a
	// different process is shown, so the whole canvas is laid out afresh each time. Every route is used
	// for the layout, so switching the error routes on or off never moves a node.
	const laidOut = $derived(layoutJourneyGraph(graph.nodes, graph.edges).nodes);

	// Every state is placed first and then the hidden ones are taken away, so hiding the error routes only
	// removes things and never moves a box.
	const shown = $derived(visibleGraph(graph, showErrorRoutes));
	const shownIds = $derived(new Set(shown.nodes.map((node) => node.id)));

	// The selected flag is set here, not by Svelte Flow, so the list of steps and the graph always agree
	// about which state is highlighted.
	const nodes = $derived(
		laidOut
			.filter((node) => shownIds.has(node.id))
			.map((node) => ({ ...node, selected: node.data.stateId === selectedStateId }))
	);
</script>

<section class="process-graph" aria-label="Process graph">
	<SvelteFlow
		{nodes}
		edges={shown.edges}
		{nodeTypes}
		fitView
		{fitViewOptions}
		minZoom={0.25}
		maxZoom={1.5}
		{defaultEdgeOptions}
		{proOptions}
		nodesDraggable={false}
		nodesConnectable={false}
		elementsSelectable={false}
		deleteKey={null}
		onnodeclick={({ node }) => {
			// A box that runs another process opens it. Any other state is highlighted.
			if (node.type === 'step' && node.data.opensProcess) {
				onOpenProcess?.(node.data.opensProcess.id);
				return;
			}
			selectedStateId = node.data.stateId ?? null;
		}}
		onpaneclick={() => (selectedStateId = null)}
	>
		<Background />
		<Controls showLock={false} />
		<MiniMap pannable zoomable />
	</SvelteFlow>
</section>

<style>
	.process-graph {
		display: flex;
		flex-direction: column;
		height: 100%;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.process-graph :global(.svelte-flow) {
		background-color: #ffffff;
	}

	/* A read only graph has nothing to connect, so the connection points are hidden. They stay in place
		because the edges are drawn from them. */
	.process-graph :global(.svelte-flow__handle) {
		opacity: 0;
		pointer-events: none;
	}
</style>
