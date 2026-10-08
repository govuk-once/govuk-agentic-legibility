import { layoutJourneyGraph, nodeSize } from './layout';
import type { JourneyEdge, JourneyGraphElements, JourneyNode } from './types';

// A node id waiting to be placed at a specific point the next time reconcileGraph runs, set right before
// the schema change that creates it (a drag from the sidebar palette, or a connection dragged out to
// empty canvas), and consumed the one time it is read. Exported so JourneyGraph.svelte's own pending map
// can be typed consistently with what reconcileGraph expects.
export type PendingPositions = Map<string, { x: number; y: number }>;

/**
 * Keeps the canvas's own node and edge state in step with a freshly built (position-less) graph from the
 * current service, without ever discarding a position the person has already chosen for a node that is
 * still there. A node whose id survives keeps its position and Svelte Flow's own runtime state
 * (selected, dragging), only its data is refreshed, so renaming a step or editing its branches never
 * moves anything on the canvas. A brand new node takes the position it was just dropped or dragged to,
 * if one is waiting for it in pendingPositions, otherwise settles near whichever existing node it shares
 * an edge with. The very first time a service is opened, with no current nodes at all, is the one
 * occasion the whole graph is auto arranged by dagre in one pass, exactly as it always has been.
 */
export function reconcileGraph(
	currentNodes: JourneyNode[],
	built: JourneyGraphElements,
	pendingPositions: PendingPositions
): { nodes: JourneyNode[]; edges: JourneyEdge[] } {
	const currentById = new Map(currentNodes.map((node) => [node.id, node]));
	const isFirstLoad = currentNodes.length === 0;

	// Tracks every node placed by something other than the neighbour fallback below, a survivor or one
	// just dropped or dragged to a specific point, so that fallback never runs a second time over a
	// position one of these two already settled.
	const alreadyPlaced = new Set<string>();

	const nodes: JourneyNode[] = built.nodes.map((builtNode) => {
		const existing = currentById.get(builtNode.id);
		if (existing) {
			alreadyPlaced.add(builtNode.id);
			return { ...existing, data: builtNode.data, type: builtNode.type } as JourneyNode;
		}

		const pending = pendingPositions.get(builtNode.id);
		if (pending) {
			pendingPositions.delete(builtNode.id);
			alreadyPlaced.add(builtNode.id);
			return { ...builtNode, position: pending, ...nodeSize(builtNode) };
		}

		return builtNode;
	});

	if (isFirstLoad) {
		const laidOut = layoutJourneyGraph(nodes, built.edges);
		return { nodes: laidOut.nodes, edges: built.edges };
	}

	positionUnplacedNeighbours(nodes, built.edges, alreadyPlaced);

	return { nodes, edges: built.edges };
}

/**
 * Settles any node that is new, and was not already given a position from pendingPositions, next to a
 * neighbour it shares an edge with that already has a real position. Only reached for a node created some
 * way other than through the page's own create handlers, which always set a pending position themselves,
 * so this is a fallback rather than the normal path: it exists so such a node is never left stacked on
 * the (0,0) placeholder serviceToGraph hands out before any layout has run.
 */
function positionUnplacedNeighbours(
	nodes: JourneyNode[],
	edges: JourneyEdge[],
	alreadyPlaced: Set<string>
): void {
	const nodeById = new Map(nodes.map((node) => [node.id, node]));

	for (const node of nodes) {
		if (alreadyPlaced.has(node.id)) continue;

		const neighbourEdge = edges.find((edge) => edge.source === node.id || edge.target === node.id);
		const neighbourId = neighbourEdge
			? neighbourEdge.source === node.id
				? neighbourEdge.target
				: neighbourEdge.source
			: undefined;
		const neighbour = neighbourId ? nodeById.get(neighbourId) : undefined;

		if (neighbour) {
			node.position = { x: neighbour.position.x + 60, y: neighbour.position.y + 100 };
			Object.assign(node, nodeSize(node));
		}
	}
}
