<script lang="ts">
	import { untrack } from 'svelte';
	import { SvelteFlow, Background, Controls, MiniMap, type Connection } from '@xyflow/svelte';
	import StepNode from './StepNode.svelte';
	import ConditionNode from './ConditionNode.svelte';
	import TerminalNode from './TerminalNode.svelte';
	import FlowBridge, { type FlowInstance } from './FlowBridge.svelte';
	import { serviceToGraph } from './service-to-graph';
	import { reconcileGraph, type PendingPositions } from './reconcile';
	import type { JourneyEdge, JourneyNode } from './types';
	import type { Service } from '$lib/schema';

	interface Props {
		service: Service;
		// Every step whose dead end is treated as a deliberate ending rather than just the current default
		// state, passed straight through to serviceToGraph. Owned by the page since it tracks history
		// across the whole editing session, not just this canvas.
		explicitEndStepIds: Set<string>;
		selectedStepId?: string | null;
		// Owned by the page, not this component, because the design's own toolbar controlling it sits above
		// the whole editor body rather than being scoped to the canvas column alone.
		showBranching?: boolean;
		// Fired when a step node is clicked, naming the step, so the page can decide what a click means
		// (today, always opening that step for editing).
		onNodeActivate?: (stepId: string) => void;
		// Fired when a connection is dragged from one node's handle to another's, naming the source in the
		// same terms handleConnectSteps already understands, a real step's id, the gateway id resolved back
		// to the step that owns it, or the sentinel 'start' for the journey's own entry point, and the real
		// step id the connection landed on.
		onConnectSteps?: (sourceStepId: string, targetStepId: string) => void;
		// Fired when a connection is dragged out to empty canvas rather than onto another node, with the
		// source resolved the same way as onConnectSteps and the flow position it was dropped at.
		onCreateConnectedStep?: (sourceStepId: string, position: { x: number; y: number }) => void;
		// Fired when the toolbar's Step item is dropped onto the canvas, with the flow position of the drop.
		onCreateStep?: (position: { x: number; y: number }) => void;
		// Fired once a draft condition, placed from the toolbar, has a real step feeding into it and at
		// least two real steps it leads to: the draft is promoted into a real gateway by giving the source
		// step these exact routes, the ones actually drawn, rather than a guess at which steps were meant.
		onAddBranchRoutes?: (sourceStepId: string, targetStepIds: string[]) => void;
		// Fired once a draft end, placed from the toolbar, is connected to a real step: the same "End the
		// journey here" action the step editor panel already offers, reached from the canvas instead.
		onSetStepEnd?: (stepId: string) => void;
		// Fired once per delete gesture (the Delete key on a selection) with every step removed outright and
		// every individual route cleared, so the page can patch dangling references and cascade the removal
		// to anything that becomes unreachable as a result, the same way it already does for the step list's
		// own remove action and for ending a journey at a step.
		onDeleteElements?: (deleted: {
			stepIds: string[];
			edges: Array<{ sourceStepId: string; targetStepId: string }>;
		}) => void;
	}

	let {
		service,
		explicitEndStepIds,
		selectedStepId = $bindable(null),
		showBranching = $bindable(true),
		onNodeActivate,
		onConnectSteps,
		onCreateConnectedStep,
		onCreateStep,
		onAddBranchRoutes,
		onSetStepEnd,
		onDeleteElements
	}: Props = $props();

	const nodeTypes = { step: StepNode, condition: ConditionNode, terminal: TerminalNode };
	// Declared once, rather than as object literals directly in the markup below, so SvelteFlow always
	// receives the same object reference for these across every reactive update, rather than a freshly
	// allocated one each time.
	const fitViewOptions = { padding: 0.15, maxZoom: 0.9 };
	const defaultEdgeOptions = { type: 'smoothstep' as const };
	const proOptions = { hideAttribution: true };

	// Off, every branching step is shown with only its first route, collapsing the rest of that branch out
	// of the picture. This never touches the real service, only what is built and laid out for display.
	const displayService = $derived(
		showBranching
			? service
			: {
					...service,
					steps: service.steps.map((step) =>
						step.transitions.length > 1 ? { ...step, transitions: step.transitions.slice(0, 1) } : step
					)
				}
	);

	// The position source of truth for the life of this editing session: seeded by dagre once, on first
	// load, then kept in step with the service by reconcileGraph rather than replaced by it, so a survives
	// node's position, and Svelte Flow's own selection and drag state, are never discarded by an unrelated
	// edit. See reconcile.ts.
	let nodes = $state.raw<JourneyNode[]>([]);
	let edges = $state.raw<JourneyEdge[]>([]);

	// A node id waiting to be placed at a specific point, set just before the schema change that creates
	// it, consumed the one time reconcileGraph next runs. A plain Map rather than state, since nothing on
	// screen needs to react to it directly, only reconcileGraph reads and clears it.
	const pendingPositions: PendingPositions = new Map();

	// Rebuilds the service-derived portion of the canvas whenever the service changes, leaving any draft
	// node or edge exactly as it is: a draft has no counterpart in the service at all, so there is nothing
	// for this to reconcile it against, it is carried across untouched until promoteDraftIfReady replaces
	// it with the real thing.
	$effect(() => {
		const built = serviceToGraph(displayService, explicitEndStepIds);
		// The current nodes and edges are read without tracking them, since this effect's job is to react
		// to the service changing, not to its own writes back into nodes and edges below.
		const reconciled = untrack(() => {
			const draftNodes = nodes.filter(isDraftNode);
			const draftNodeIds = new Set(draftNodes.map((node) => node.id));
			const realNodes = nodes.filter((node) => !draftNodeIds.has(node.id));
			const draftEdges = edges.filter((edge) => draftNodeIds.has(edge.source) || draftNodeIds.has(edge.target));

			const r = reconcileGraph(realNodes, built, pendingPositions);
			return { nodes: [...r.nodes, ...draftNodes], edges: [...r.edges, ...draftEdges] };
		});
		nodes = reconciled.nodes;
		edges = reconciled.edges;
	});

	// Keeps a step node's own selected flag in step with selectedStepId when it changes for a reason other
	// than clicking that node on the canvas, for example choosing it from the step list beside the graph.
	// Reads nodes untracked, so this only reruns when selectedStepId itself changes, never as a reaction to
	// the write it makes at its own end.
	$effect(() => {
		const id = selectedStepId;
		const current = untrack(() => nodes);
		let changed = false;
		const updated = current.map((node) => {
			const isSelected = node.type === 'step' && node.data.stepId === id;
			if (node.selected === isSelected) return node;
			changed = true;
			return { ...node, selected: isSelected } as JourneyNode;
		});
		if (changed) nodes = updated;
	});

	let flowInstance: FlowInstance | undefined;

	// Places a brand new node the next time reconcileGraph runs, called by the page right before it makes
	// the schema change that creates the step, so the node appears exactly where it was dropped or dragged
	// to rather than wherever a fallback layout would otherwise put it.
	export function placeNextNodeAt(id: string, position: { x: number; y: number }) {
		pendingPositions.set(id, position);
	}

	/**
	 * True for a condition, start or end node placed from the toolbar that has not yet been promoted: it
	 * exists only on this canvas, not in the service, until enough of the right connections make it real.
	 * See promoteDraftIfReady.
	 */
	function isDraftNode(node: JourneyNode): boolean {
		return (node.type === 'condition' || node.type === 'terminal') && node.data.draft === true;
	}

	/**
	 * Resolves a canvas node id back to the step id it represents in handleConnectSteps' own terms: a step
	 * node's own id, the sentinel 'start' for the journey's entry terminal, or, for a gateway, the step that
	 * owns it, found via the one sequence edge leading into it, since a gateway holds no step id of its own.
	 * A draft node resolves to nothing: it is not a real step, or the real 'start', until it is promoted.
	 */
	function resolveSourceStepId(nodeId: string | null | undefined): string | null {
		if (!nodeId) return null;
		const node = nodes.find((candidate) => candidate.id === nodeId);
		if (!node || isDraftNode(node)) return null;
		if (node.type === 'step') return node.data.stepId ?? null;
		if (node.type === 'terminal') return node.data.appearance === 'start' ? 'start' : null;

		const ownerEdge = edges.find((edge) => edge.target === node.id && edge.data?.kind === 'sequence');
		return ownerEdge ? resolveSourceStepId(ownerEdge.source) : null;
	}

	// Two drafts cannot connect to each other, only a real step and a draft can, since a draft only ever
	// becomes real by attaching to an actual step on at least one end. Between two real nodes, the target
	// must be a real step: a terminal has no routes of its own to receive one, and a gateway is synthesised
	// from a step already having two or more, never a target chosen by hand. A step connecting to itself is
	// rejected too, since a route from a step back to itself describes nothing a real journey does.
	function isValidConnection(connection: JourneyEdge | Connection): boolean {
		if (connection.source === connection.target) return false;
		const sourceNode = nodes.find((node) => node.id === connection.source);
		const targetNode = nodes.find((node) => node.id === connection.target);
		if (!sourceNode || !targetNode) return false;

		const sourceIsDraft = isDraftNode(sourceNode);
		const targetIsDraft = isDraftNode(targetNode);
		if (sourceIsDraft && targetIsDraft) return false;
		if (sourceIsDraft) return targetNode.type === 'step';
		if (targetIsDraft) return sourceNode.type === 'step';

		return targetNode.type === 'step';
	}

	function handleConnect(connection: Connection) {
		const sourceNode = nodes.find((node) => node.id === connection.source);
		const targetNode = nodes.find((node) => node.id === connection.target);
		if (!sourceNode || !targetNode) return;

		if (!isDraftNode(sourceNode) && !isDraftNode(targetNode)) {
			const sourceStepId = resolveSourceStepId(connection.source);
			if (!sourceStepId || targetNode.type !== 'step' || !targetNode.data.stepId) return;
			onConnectSteps?.(sourceStepId, targetNode.data.stepId);
			return;
		}

		// One end is a draft: this connection is not a real route yet, only recorded on the canvas, until
		// the draft it touches has enough real connections to promote.
		const draftEdgeId = `draft-edge-${connection.source}-${connection.target}`;
		if (edges.some((edge) => edge.id === draftEdgeId)) return;
		edges = [
			...edges,
			{ id: draftEdgeId, source: connection.source, target: connection.target, data: { kind: 'sequence', draft: true } }
		];

		promoteDraftIfReady(isDraftNode(sourceNode) ? sourceNode : targetNode);
	}

	/**
	 * Checks whether a draft node now has enough real connections to become part of the service, and if so,
	 * applies that change and removes the draft: a start once it has one connection to a real step
	 * (reassigning the entry point, the same as connecting from the real start terminal), an end once it
	 * has one connection from a real step (clearing that step's routes), and a condition once it has one
	 * real step feeding in and at least two real steps it leads to (giving the source step those exact
	 * routes). Anything short of that is left as it is, still just a draft.
	 */
	function promoteDraftIfReady(draft: JourneyNode) {
		if (draft.type === 'terminal' && draft.data.appearance === 'start') {
			const outgoing = edges.find((edge) => edge.source === draft.id);
			const targetNode = outgoing && nodes.find((node) => node.id === outgoing.target);
			if (targetNode?.type !== 'step' || !targetNode.data.stepId) return;
			onConnectSteps?.('start', targetNode.data.stepId);
			removeDraft(draft.id);
			return;
		}

		if (draft.type === 'terminal' && draft.data.appearance === 'end') {
			const incoming = edges.find((edge) => edge.target === draft.id);
			const sourceStepId = incoming && resolveSourceStepId(incoming.source);
			if (!sourceStepId) return;
			onSetStepEnd?.(sourceStepId);
			removeDraft(draft.id);
			return;
		}

		if (draft.type === 'condition') {
			const incoming = edges.find((edge) => edge.target === draft.id);
			const sourceStepId = incoming && resolveSourceStepId(incoming.source);
			if (!sourceStepId) return;

			const targetStepIds = [
				...new Set(
					edges
						.filter((edge) => edge.source === draft.id)
						.flatMap((edge) => {
							const targetNode = nodes.find((node) => node.id === edge.target);
							return targetNode?.type === 'step' && targetNode.data.stepId ? [targetNode.data.stepId] : [];
						})
				)
			];
			if (targetStepIds.length < 2) return;

			onAddBranchRoutes?.(sourceStepId, targetStepIds);
			removeDraft(draft.id);
		}
	}

	/**
	 * Removes a draft node once it has been promoted, along with every draft edge touching it: the real
	 * gateway, entry point or ended step the promotion just wrote takes its place on the next reconcile,
	 * see reconcile.ts.
	 */
	function removeDraft(nodeId: string) {
		nodes = nodes.filter((node) => node.id !== nodeId);
		edges = edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId);
	}

	async function handleBeforeDelete({
		nodes: deletedNodes,
		edges: deletedEdges
	}: {
		nodes: JourneyNode[];
		edges: JourneyEdge[];
	}) {
		// A draft node or edge has no counterpart in the service at all, so deleting one is just removing it
		// from the canvas, nothing for the page to apply.
		const draftNodeIds = new Set(deletedNodes.filter(isDraftNode).map((node) => node.id));
		const isDraftEdge = (edge: JourneyEdge) => edge.data?.draft || draftNodeIds.has(edge.source) || draftNodeIds.has(edge.target);
		const draftEdgeIds = new Set(deletedEdges.filter(isDraftEdge).map((edge) => edge.id));
		if (draftNodeIds.size > 0 || draftEdgeIds.size > 0) {
			nodes = nodes.filter((node) => !draftNodeIds.has(node.id));
			edges = edges.filter((edge) => !draftEdgeIds.has(edge.id));
		}

		const realNodes = deletedNodes.filter((node) => !draftNodeIds.has(node.id));
		const realEdges = deletedEdges.filter((edge) => !draftEdgeIds.has(edge.id));

		const stepIds = realNodes.flatMap((node) => (node.type === 'step' && node.data.stepId ? [node.data.stepId] : []));

		// Only an edge that both starts somewhere real and lands on an actual step is a route worth clearing:
		// this leaves out the structural edge from a step into its own gateway, and the journey's own entry
		// edge from 'start', neither of which is a route the step editor can point somewhere else on its own.
		const edgesToClear = realEdges.flatMap((edge) => {
			const sourceStepId = resolveSourceStepId(edge.source);
			const targetNode = nodes.find((node) => node.id === edge.target);
			if (!sourceStepId || sourceStepId === 'start' || targetNode?.type !== 'step' || !targetNode.data.stepId) {
				return [];
			}
			return [{ sourceStepId, targetStepId: targetNode.data.stepId }];
		});

		if (stepIds.length > 0 || edgesToClear.length > 0) {
			onDeleteElements?.({ stepIds, edges: edgesToClear });
		}

		// Deleting a real gateway diamond collapses it: the step it belongs to loses every route it
		// currently branches into, the same as ending the journey there, since a diamond feeding out of a
		// step but leading nowhere is not a shape this canvas can otherwise represent.
		for (const node of realNodes) {
			if (node.type !== 'condition') continue;
			const ownerStepId = resolveSourceStepId(node.id);
			if (ownerStepId) onSetStepEnd?.(ownerStepId);
		}

		// The schema mutation above, once applied by the page, flows back through the reconcile effect and
		// rebuilds nodes and edges to match, so Svelte Flow's own default deletion is always declined here.
		return false;
	}

	function handleDragOver(event: DragEvent) {
		if (event.dataTransfer?.types.includes('application/x-journey-node')) {
			event.preventDefault();
		}
	}

	/**
	 * Drops one of the toolbar's four shapes at the flow position it landed on, independent of whatever
	 * else is already on the canvas there. A step is real immediately, since an unconnected step is
	 * already a perfectly ordinary thing for the service to contain. A condition, start or end instead
	 * starts life as a draft, existing only here until connecting it up promotes it, see
	 * promoteDraftIfReady: there is no such thing as a gateway with nothing feeding into it, a second entry
	 * point, or an ending nothing leads to, so none of the three can be written to the service on their own.
	 */
	function handleDrop(event: DragEvent) {
		const tool = event.dataTransfer?.getData('application/x-journey-node');
		if (!tool || !flowInstance) return;
		event.preventDefault();
		const position = flowInstance.screenToFlowPosition({ x: event.clientX, y: event.clientY });

		if (tool === 'step') {
			onCreateStep?.(position);
			return;
		}

		if (tool !== 'condition' && tool !== 'start' && tool !== 'end') return;
		const id = `draft-${crypto.randomUUID()}`;
		const draftNode: JourneyNode =
			tool === 'condition'
				? { id, type: 'condition', position, data: { ariaLabel: 'Draft condition, not yet connected', draft: true } }
				: {
						id,
						type: 'terminal',
						position,
						data: {
							label: tool === 'start' ? 'Start' : 'End',
							appearance: tool,
							ariaLabel: `Draft ${tool}, not yet connected`,
							draft: true
						}
					};
		nodes = [...nodes, draftNode];
	}
</script>

<section class="journey-graph" aria-label="Journey graph">
	<SvelteFlow
		bind:nodes
		bind:edges
		{nodeTypes}
		fitView
		{fitViewOptions}
		minZoom={0.25}
		maxZoom={1.5}
		{defaultEdgeOptions}
		{proOptions}
		{isValidConnection}
		onconnect={handleConnect}
		onconnectend={(_event, connectionState) => {
			// A connection dropped onto empty canvas, rather than another node's handle, creates a new step
			// instead of linking to an existing one. Only a drag that started from a source handle is treated
			// this way: a step's own routes always run forward, so there is no equivalent gesture for a drag
			// that started from a target handle.
			if (connectionState.toNode || !connectionState.to) return;
			if (connectionState.fromHandle?.type !== 'source') return;
			const sourceStepId = resolveSourceStepId(connectionState.fromNode?.id);
			if (!sourceStepId) return;
			onCreateConnectedStep?.(sourceStepId, connectionState.to);
		}}
		onbeforedelete={handleBeforeDelete}
		onnodeclick={({ node }) => {
			if (node.type === 'step' && node.data.stepId) onNodeActivate?.(node.data.stepId);
		}}
		ondragover={handleDragOver}
		ondrop={handleDrop}
	>
		<FlowBridge
			onready={(instance) => {
				flowInstance = instance;
			}}
		/>
		<Background />
		<Controls />
		<MiniMap pannable zoomable />
	</SvelteFlow>
</section>

<style>
	.journey-graph {
		display: flex;
		flex-direction: column;
		height: 100%;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.journey-graph :global(.svelte-flow) {
		background-color: #ffffff;
	}

	/* A small solid dot at rest, always visible, the same as Figma's own connection points. Growing on
		hover, rather than needing the hover to reveal it in the first place, is what signals a particular
		one is now ready to grab and drag: the "+" glyph inside only appears once it has grown large enough
		to actually carry it legibly. Centralised here rather than repeating it in every node component that
		uses a handle. */
	.journey-graph :global(.svelte-flow__handle) {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 10px;
		height: 10px;
		background-color: #1d70b8;
		border: none;
		border-radius: 50%;
		transition: width 0.12s ease-in-out, height 0.12s ease-in-out;
	}

	.journey-graph :global(.svelte-flow__handle:hover) {
		width: 28px;
		height: 28px;
	}

	.journey-graph :global(.journey-node-handle-hint) {
		opacity: 0;
		font-size: 1rem;
		font-weight: 700;
		line-height: 1;
		color: #ffffff;
		pointer-events: none;
		transition: opacity 0.1s ease-in-out;
	}

	.journey-graph :global(.svelte-flow__handle:hover .journey-node-handle-hint) {
		opacity: 1;
	}
</style>
