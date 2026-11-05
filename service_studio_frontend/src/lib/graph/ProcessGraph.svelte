<script lang="ts">
	import { SvelteFlow, Background, Controls, MarkerType, MiniMap } from '@xyflow/svelte';
	import StepNode from './StepNode.svelte';
	import ConditionNode from './ConditionNode.svelte';
	import TerminalNode from './TerminalNode.svelte';
	import { layoutJourneyGraph, processLayoutOptions } from './layout';
	import { graphShape, separateEndDots, visibleGraph } from './process-to-graph';
	import type { NodePositions, ProcessGraphElements } from './process-graph-types';

	interface Props {
		// The nodes and edges of the process, built by the component that owns it so the list of states uses the same ones.
		graph: ProcessGraphElements;
		// The state highlighted on the graph, shared with the list of states. Null when nothing is selected.
		selectedStateId?: string | null;
		// Off by default, which hides the routes taken when something goes wrong or runs late, and the
		// states that only those routes lead to. The graph is arranged again when this changes.
		showErrorRoutes?: boolean;
		// Where the person has dragged boxes to. A box that is not listed stays where the layout put it.
		positions?: NodePositions;
		// Called with the new position of every box that was just dragged, when the drag ends.
		onMoveNodes?: (moved: NodePositions) => void;
		// Called with the id of the process an invoke box runs, when the box is clicked.
		onOpenProcess?: (processId: string) => void;
	}

	let {
		graph,
		selectedStateId = $bindable(null),
		showErrorRoutes = false,
		positions = {},
		onMoveNodes,
		onOpenProcess
	}: Props = $props();

	// The same three node components as the original graph, so a state looks the same in either.
	const nodeTypes = { step: StepNode, condition: ConditionNode, terminal: TerminalNode };

	// Declared once so Svelte Flow receives the same object on every update. The arrow head shows the
	// direction of a route, which matters when a route loops back to an earlier state.
	const fitViewOptions = { padding: 0.15, maxZoom: 0.9 };
	const defaultEdgeOptions = { type: 'smoothstep' as const, markerEnd: { type: MarkerType.ArrowClosed } };
	const proOptions = { hideAttribution: true };

	// What is shown, with the error routes on or off. Only this is laid out, so a hidden error route cannot
	// pull a box sideways. Ticking Show error routes lays the graph out again with those routes in it.
	// An end state that several steps lead to is drawn as one end dot under each step, so no line has to run
	// a long way across the graph to reach it.
	const shown = $derived(separateEndDots(visibleGraph(graph, showErrorRoutes)));

	// Where the layout put each box, and the shape of the graph it was worked out for. An edit that leaves the
	// shape as it was, such as a new title, reuses these places, so a rename never moves a box. The graph is
	// arranged again only when a box or a line is added, removed or moved. This is plain bookkeeping and not
	// state, because nothing needs to react to it changing.
	let lastLayout: { shape: string; places: Map<string, { x: number; y: number }> } | undefined;

	const laidOut = $derived.by(() => {
		const shape = graphShape(shown);
		const places = lastLayout?.shape === shape ? lastLayout.places : undefined;
		if (places) return shown.nodes.map((node) => ({ ...node, position: places.get(node.id) ?? node.position }));

		const nodes = layoutJourneyGraph(shown.nodes, shown.edges, processLayoutOptions).nodes;
		lastLayout = { shape, places: new Map(nodes.map((node) => [node.id, node.position])) };
		return nodes;
	});

	// A box the person has dragged keeps its place, and every other box stays where the layout put it. The
	// selected flag is set here, not by Svelte Flow, so the list of steps and the graph always agree about
	// which state is highlighted.
	const nodes = $derived(
		laidOut.map((node) => ({
			...node,
			position: positions[node.id] ?? node.position,
			selected: node.data.stateId === selectedStateId
		}))
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
		nodesDraggable
		onnodedragstop={({ nodes: dragged }) => onMoveNodes?.(Object.fromEntries(dragged.map((node) => [node.id, node.position])))}
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
