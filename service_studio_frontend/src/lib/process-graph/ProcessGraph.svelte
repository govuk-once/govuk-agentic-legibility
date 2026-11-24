<script lang="ts">
	import { SvelteFlow, Background, Controls, MarkerType, MiniMap, type Edge, type Node } from '@xyflow/svelte';
	import StepNode from '$lib/graph-kit/StepNode.svelte';
	import ConditionNode from '$lib/graph-kit/ConditionNode.svelte';
	import TerminalNode from '$lib/graph-kit/TerminalNode.svelte';
	import ModuleBorderNode from '$lib/graph-kit/ModuleBorderNode.svelte';
	import FlowPositionBridge, { type FlowInstance } from '$lib/graph-kit/FlowPositionBridge.svelte';
	import ProblemStrip from './ProblemStrip.svelte';
	import { nodeSize } from '$lib/graph-kit/layout';
	import { arrangeProcessGraph, placeBesideNeighbours } from './arrange';
	import type { Draft, DraftSet, Endpoint } from './drafts';
	import { moduleBorderNodeType, moduleBorders } from './module-borders';
	import { separateEndDots, startNodeId, visibleGraph } from './process-to-graph';
	import type { DeletedElements, NodePositions, ProblemMark, ProcessGraphElements, ProcessNode, StepOutlineColours } from './process-graph-types';

	interface Props {
		// The nodes and edges of the process, built by the component that owns it so the list of states uses the same ones.
		graph: ProcessGraphElements;
		// The state highlighted on the graph, shared with the list of states. Null when nothing is selected.
		selectedStateId?: string | null;
		// Off by default, which hides the routes taken when something goes wrong or runs late, and the
		// states that only those routes lead to. The graph is arranged again when this changes.
		showErrorRoutes?: boolean;
		// On by default, so every developer step the graph was built with is drawn. Off hides them, and the line before
		// each one carries on to the state after it. The graph is arranged again when this changes.
		showDeveloperSteps?: boolean;
		// The colour of the outline of a box, for each kind of state the editor wants to tell apart. A kind that is
		// not listed keeps the usual grey outline.
		stepOutlineColours?: StepOutlineColours;
		// Where the person has dragged or dropped boxes to. A box that is not listed stays where it was placed.
		positions?: NodePositions;
		// Changing this number arranges the whole graph again, for example after a step is moved in the journey.
		layoutRound?: number;
		// Called with the new position of every box that was just dragged, when the drag ends.
		onMoveNodes?: (moved: NodePositions) => void;
		// Called with the id of the process an invoke box runs, when the box is clicked.
		onOpenProcess?: (processId: string) => void;
		// The shapes placed from the palette that are not in the process yet, and the lines drawn to them.
		drafts?: DraftSet;
		// Says whether a line from one end to another may be drawn. It is asked while a line is being dragged,
		// so a line that cannot be drawn never snaps onto a shape.
		canConnect?: (source: Endpoint, target: Endpoint) => boolean;
		// Called with the two ends when a line is drawn from one shape to another.
		onConnect?: (source: Endpoint, target: Endpoint) => void;
		// Called with the end a line was dragged from and the place it was let go, when that is empty canvas.
		onCreateConnectedStep?: (source: Endpoint, position: { x: number; y: number }) => void;
		// Called with the value of the palette shape that was dropped and the place on the canvas where it landed. The
		// component that holds the palette knows what each value stands for, so it decides what is added.
		onDropShape?: (value: string, position: { x: number; y: number }) => void;
		// Called once for each press of the Delete key with everything that was selected: draft shapes and lines,
		// states of the process, and the lines between states. The page decides what each one means.
		onDeleteElements?: (deleted: DeletedElements) => void;
		// The problems to mark on a strip down the right edge of the canvas. The strip is only drawn while there is a
		// problem to mark, so an editor that gives none, or a journey with no problems, has no strip.
		problemMarks?: ProblemMark[];
	}

	let {
		graph,
		selectedStateId = $bindable(null),
		showErrorRoutes = false,
		showDeveloperSteps = true,
		stepOutlineColours = {},
		positions = {},
		layoutRound = 0,
		onMoveNodes,
		onOpenProcess,
		drafts = { drafts: [], lines: [] },
		canConnect,
		onConnect,
		onCreateConnectedStep,
		onDropShape,
		onDeleteElements,
		problemMarks
	}: Props = $props();

	// The node components for a step, a decision and the start and end dots are shared with the other graph editor,
	// so a state looks the same in either. The border is drawn round the states of one copy of a module.
	const nodeTypes = { step: StepNode, condition: ConditionNode, terminal: TerminalNode, [moduleBorderNodeType]: ModuleBorderNode };

	// Declared once so Svelte Flow receives the same object on every update. The arrow head shows the
	// direction of a route, which matters when a route loops back to an earlier state.
	const fitViewOptions = { padding: 0.15, maxZoom: 0.9 };
	const defaultEdgeOptions = { type: 'smoothstep' as const, markerEnd: { type: MarkerType.ArrowClosed } };
	const proOptions = { hideAttribution: true };
	// Either key takes out what is selected, because a keyboard may have only one of them.
	const deleteKeys = ['Delete', 'Backspace'];

	// What is shown, with the error routes on or off. Only this is laid out, so a hidden error route cannot
	// pull a box sideways. Ticking Show error routes lays the graph out again with those routes in it.
	// An end state that several steps lead to is drawn as one end dot under each step, so no line has to run
	// a long way across the graph to reach it.
	const shown = $derived(separateEndDots(visibleGraph(graph, { showErrorRoutes, showDeveloperSteps })));

	// Where each box sits, and the round of arranging that placed them. The whole graph is arranged when it is first
	// drawn and again when layoutRound changes. Between those a box keeps its place, so adding or removing one box
	// or line never moves the others. This is plain bookkeeping and not state, because nothing needs to react to it.
	let arrangement: { round: number; places: Map<string, { x: number; y: number }> } | undefined;

	const laidOut = $derived.by(() => {
		if (arrangement?.round !== layoutRound) {
			const nodes = arrangeProcessGraph(shown.nodes, shown.edges).nodes;
			arrangement = { round: layoutRound, places: new Map(nodes.map((node) => [node.id, node.position])) };
			return nodes;
		}

		// A box that is new since the graph was arranged goes where it was dropped, or beside a box it is joined to. A
		// box joined to nothing that has a place, which is rare, takes the place a full arrangement would give it.
		const { places } = arrangement;
		const placeOf = (id: string) => positions[id] ?? places.get(id);
		const beside = placeBesideNeighbours(shown.nodes, shown.edges, placeOf);
		const unjoined = shown.nodes.some((node) => !placeOf(node.id) && !beside.has(node.id));
		const arranged = unjoined ? new Map(arrangeProcessGraph(shown.nodes, shown.edges).nodes.map((node) => [node.id, node.position])) : undefined;

		// The size is set on each node as the layout sets it, because Svelte Flow sizes the box and places its
		// handles from it.
		const nodes = shown.nodes.map((node) => ({
			...node,
			...nodeSize(node),
			position: placeOf(node.id) ?? beside.get(node.id) ?? arranged?.get(node.id) ?? node.position
		}));
		arrangement = { round: layoutRound, places: new Map(nodes.map((node) => [node.id, node.position])) };
		return nodes;
	});

	// The shapes placed from the palette, drawn where they were dropped or dragged to. They are not laid out,
	// because the person chose where each one goes.
	const draftNodes = $derived(drafts.drafts.map((draft) => draftNode(draft)));

	// A box the person has dragged keeps its place, and every other box stays where it was placed. The
	// selected flag is set here for a state, so the list of steps and the graph always agree about which
	// state is highlighted.
	// The module being dragged by the move symbol on its border: its group id, where the border was when the drag began,
	// and how far it has moved since. Every shape of that module is drawn moved by the same amount while the drag
	// lasts, and the border follows them, because it is worked out from where they are.
	let moduleDrag = $state<{ groupId: string; start: { x: number; y: number }; offset: { x: number; y: number } }>();

	/**
	 * Gives where a shape is drawn: where the person dragged it to, or where it was placed, moved along with its
	 * module while the module is being dragged by its move symbol.
	 */
	function positionOf(node: ProcessNode): { x: number; y: number } {
		const place = positions[node.id] ?? node.position;
		if (!moduleDrag || node.data.moduleGroup?.id !== moduleDrag.groupId) return place;
		return { x: place.x + moduleDrag.offset.x, y: place.y + moduleDrag.offset.y };
	}

	// The borders round the states of each copy of a module come first, so they are drawn behind the shapes.
	const nodes = $derived<Node[]>([
		...moduleBorders(laidOut, positionOf),
		...laidOut.map((node) => ({
			...node,
			data: withOutlineColour(node),
			position: positionOf(node),
			selected: node.data.stateId === selectedStateId
		})),
		...draftNodes.map((node) => ({ ...node, position: positions[node.id] ?? node.position }))
	]);

	// The lines drawn to and from the shapes placed from the palette. A line to a state that is not on the
	// graph, because only an error route leads to it, is left out until that state is shown.
	const draftEdges = $derived<Edge[]>(
		drafts.lines.flatMap((line) => {
			const source = nodeIdOf(line.source);
			const target = nodeIdOf(line.target);
			if (!source || !target) return [];
			return [{ id: line.id, source, target, data: { kind: 'next', draft: true }, style: 'stroke-dasharray: 6 4' }];
		})
	);

	const edges = $derived<Edge[]>([...shown.edges, ...draftEdges]);

	// Where the canvas is on the screen, so a shape dropped from the palette lands where the pointer was.
	let flowInstance: FlowInstance | undefined;

	/**
	 * Returns the data of a node, with the outline colour the editor chose for its kind of state when it is a box
	 * of a kind that has one. Every other node keeps the data it had.
	 */
	function withOutlineColour(node: ProcessNode): ProcessNode['data'] {
		const outlineColour = node.type === 'step' ? stepOutlineColours[node.data.stateType] : undefined;
		return outlineColour ? { ...node.data, outlineColour } : node.data;
	}

	/**
	 * Builds the node a draft is drawn as: the usual diamond or dot, drawn dashed. The id is the draft's own,
	 * which no state can have.
	 */
	function draftNode(draft: Draft): Node {
		if (draft.kind === 'condition') {
			return { id: draft.id, type: 'condition', position: draft.position, data: { ariaLabel: 'Draft decision, not yet joined', draft: true } };
		}
		const label = draft.kind === 'start' ? 'Start' : 'End';
		return {
			id: draft.id,
			type: 'terminal',
			position: draft.position,
			data: { label, appearance: draft.kind, ariaLabel: `Draft ${draft.kind}, not yet joined`, draft: true }
		};
	}

	/**
	 * Finds what a box on the canvas stands for: the start dot, a draft, or a state of the process. An end dot
	 * that was split into one dot under each step still stands for the one end state.
	 */
	function endpointOf(nodeId: string | null | undefined): Endpoint | undefined {
		if (nodeId === startNodeId) return { kind: 'start' };
		if (drafts.drafts.some((draft) => draft.id === nodeId)) return { kind: 'draft', id: nodeId as string };

		const code = shown.nodes.find((node) => node.id === nodeId)?.data.stateId;
		return code ? { kind: 'state', code } : undefined;
	}

	/**
	 * Finds the box on the canvas for one end of a line, so a line drawn to a shape can be drawn on screen.
	 */
	function nodeIdOf(end: Endpoint): string | undefined {
		if (end.kind === 'start') return startNodeId;
		if (end.kind === 'draft') return end.id;
		return shown.nodes.find((node) => node.data.stateId === end.code)?.id;
	}

	/**
	 * Tells Svelte Flow whether a line being dragged may land where it is. It only does when both ends are
	 * something the page can draw a line for and the page agrees, so a refused line never snaps on.
	 */
	function isValidConnection(connection: { source: string; target: string }): boolean {
		const source = endpointOf(connection.source);
		const target = endpointOf(connection.target);
		return source !== undefined && target !== undefined && (canConnect?.(source, target) ?? true);
	}

	/**
	 * Lets a shape from the palette be dropped on the canvas. Only a drag that came from the palette is accepted.
	 */
	function handleDragOver(event: DragEvent) {
		if (event.dataTransfer?.types.includes('application/x-journey-node')) event.preventDefault();
	}

	/**
	 * Hands over the palette shape that was dropped, with the place on the canvas where it landed. The drop carries
	 * the value of the shape, and the place on the screen is turned into a place on the canvas.
	 */
	function handleDrop(event: DragEvent) {
		const value = event.dataTransfer?.getData('application/x-journey-node');
		if (!value || !flowInstance) return;

		event.preventDefault();
		onDropShape?.(value, flowInstance.screenToFlowPosition({ x: event.clientX, y: event.clientY }));
	}

	/**
	 * Works out what a press of the Delete key removes and hands it to the page. Svelte Flow's own removal is
	 * always declined, because the page changes the process and the graph is then built again from it.
	 */
	async function handleBeforeDelete({ nodes: deletedNodes, edges: deletedEdges }: { nodes: Node[]; edges: Edge[] }) {
		const draftIds = deletedNodes.filter((node) => drafts.drafts.some((draft) => draft.id === node.id)).map((node) => node.id);
		const draftLineIds = deletedEdges.filter((edge) => edge.data?.draft).map((edge) => edge.id);

		const stateCodes = [
			...new Set(
				deletedNodes.flatMap((node) => {
					const end = endpointOf(node.id);
					return end?.kind === 'state' ? [end.code] : [];
				})
			)
		];

		// A line is only worth deleting by itself when neither end is being deleted with it, because deleting a
		// state already takes its lines with it.
		const lines = deletedEdges.flatMap((edge) => {
			const path = edge.data?.path as (string | number)[] | undefined;
			const source = endpointOf(edge.source);
			const target = endpointOf(edge.target);
			if (edge.data?.draft || !path || source?.kind !== 'state' || target?.kind !== 'state') return [];
			if (stateCodes.includes(source.code) || stateCodes.includes(target.code)) return [];
			return [{ source: source.code, path, target: target.code }];
		});

		if (draftIds.length + draftLineIds.length + stateCodes.length + lines.length > 0) {
			onDeleteElements?.({ draftIds, draftLineIds, stateCodes, lines });
		}
		return false;
	}
</script>

<section class="process-graph" aria-label="Process graph">
	<SvelteFlow
		{nodes}
		{edges}
		{nodeTypes}
		fitView
		{fitViewOptions}
		minZoom={0.25}
		maxZoom={1.5}
		{defaultEdgeOptions}
		{proOptions}
		nodesDraggable
		onnodedragstart={({ targetNode }) => {
			const groupId = targetNode?.type === moduleBorderNodeType ? targetNode.data.groupId : undefined;
			if (!targetNode || typeof groupId !== 'string') return;
			moduleDrag = { groupId, start: targetNode.position, offset: { x: 0, y: 0 } };
		}}
		onnodedrag={({ targetNode }) => {
			if (!moduleDrag || targetNode?.type !== moduleBorderNodeType) return;
			moduleDrag.offset = { x: targetNode.position.x - moduleDrag.start.x, y: targetNode.position.y - moduleDrag.start.y };
		}}
		onnodedragstop={({ nodes: dragged }) => {
			// A module dragged by its move symbol keeps every shape where it was let go. The border itself has no place of its
			// own to keep, because it is worked out from the shapes.
			if (moduleDrag) {
				const { groupId } = moduleDrag;
				const moved = laidOut.filter((node) => node.data.moduleGroup?.id === groupId);
				onMoveNodes?.(Object.fromEntries(moved.map((node) => [node.id, positionOf(node)])));
				moduleDrag = undefined;
				return;
			}
			onMoveNodes?.(Object.fromEntries(dragged.map((node) => [node.id, node.position])));
		}}
		{isValidConnection}
		onconnect={({ source, target }) => {
			const from = endpointOf(source);
			const to = endpointOf(target);
			if (from && to) onConnect?.(from, to);
		}}
		onconnectend={(_event, connectionState) => {
			// A line let go on empty canvas, and not on a shape, starts a new step there. Only a line dragged out
			// of a bottom connection point counts, because a route always runs forward from there.
			if (connectionState.toNode || connectionState.isValid || !connectionState.to) return;
			if (connectionState.fromHandle?.type !== 'source') return;

			const from = endpointOf(connectionState.fromNode?.id);
			if (from) onCreateConnectedStep?.(from, connectionState.to);
		}}
		onbeforedelete={handleBeforeDelete}
		deleteKey={deleteKeys}
		ondragover={handleDragOver}
		ondrop={handleDrop}
		onnodeclick={({ node }) => {
			// A box that runs another process opens it. Any other state is highlighted.
			const opens = node.data.opensProcess as { id: string } | undefined;
			if (node.type === 'step' && opens) {
				onOpenProcess?.(opens.id);
				return;
			}
			const end = endpointOf(node.id);
			selectedStateId = end?.kind === 'state' ? end.code : null;
		}}
		onpaneclick={() => (selectedStateId = null)}
	>
		<FlowPositionBridge onready={(instance) => (flowInstance = instance)} />
		<!-- <Background /> -->
		 <Background gap={25} size={1.5} patternColor="#646462" />
		<Controls showLock={false} />
		<MiniMap pannable zoomable position="bottom-left" class="process-graph__minimap" />
		{#if problemMarks && problemMarks.length > 0}
			<ProblemStrip marks={problemMarks} />
		{/if}
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

	/* The small map of the graph sits at the bottom left, beside the zoom buttons, where the canvas has the most room.
		It is moved right by the width of the buttons and the gap on either side of them, so it does not cover them. */
	.process-graph :global(.process-graph__minimap) {
		margin-left: 55px;
	}

	/* A small dot at each connection point that grows when the pointer is over it, so it is clear which one
		is ready to be dragged from. The plus sign only shows once the dot is big enough to hold it. */
	.process-graph :global(.svelte-flow__handle) {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 10px;
		height: 10px;
		background-color: #1d70b8;
		border: none;
		border-radius: 50%;
		transition:
			width 0.12s ease-in-out,
			height 0.12s ease-in-out;
	}

	.process-graph :global(.svelte-flow__handle:hover) {
		width: 28px;
		height: 28px;
	}

	.process-graph :global(.journey-node-handle-hint) {
		opacity: 0;
		font-size: 1rem;
		font-weight: 700;
		line-height: 1;
		color: #ffffff;
		pointer-events: none;
		transition: opacity 0.1s ease-in-out;
	}

	.process-graph :global(.svelte-flow__handle:hover .journey-node-handle-hint) {
		opacity: 1;
	}
</style>
