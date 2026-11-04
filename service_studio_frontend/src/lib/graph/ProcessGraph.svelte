<script lang="ts">
	import { SvelteFlow, Background, Controls, MarkerType, MiniMap } from '@xyflow/svelte';
	import type { Process } from '$lib/schema/workflow/process';
	import StepNode from './StepNode.svelte';
	import ConditionNode from './ConditionNode.svelte';
	import TerminalNode from './TerminalNode.svelte';
	import { layoutJourneyGraph } from './layout';
	import { processToGraph } from './process-to-graph';

	interface Props {
		process: Process;
	}

	let { process }: Props = $props();

	// The same three node components as the original graph, so a state looks the same in either.
	const nodeTypes = { step: StepNode, condition: ConditionNode, terminal: TerminalNode };

	// Declared once so Svelte Flow receives the same object on every update. The arrow head shows the
	// direction of a route, which matters when a route loops back to an earlier state.
	const fitViewOptions = { padding: 0.15, maxZoom: 0.9 };
	const defaultEdgeOptions = { type: 'smoothstep' as const, markerEnd: { type: MarkerType.ArrowClosed } };
	const proOptions = { hideAttribution: true };

	// The graph for the chosen process, with every node given a position. It is worked out again when a
	// different process is shown, so the whole canvas is laid out afresh each time.
	const graph = $derived.by(() => {
		const { nodes, edges } = processToGraph(process);
		return { nodes: layoutJourneyGraph(nodes, edges).nodes, edges };
	});
</script>

<section class="process-graph" aria-label="Process graph">
	<SvelteFlow
		nodes={graph.nodes}
		edges={graph.edges}
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
