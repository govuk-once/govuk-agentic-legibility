import dagre from '@dagrejs/dagre';
import type { ProcessNode } from './process-graph-types';
import type { JourneyNode } from './types';

// The layout reads only the type, the id and the step size of a node, and only the two ends of an edge.
// The original graph and the process graph both have the same three node kinds with those fields, so one
// layout serves both and is not copied. The original graph is removed when the editor is replaced.
type LayoutNode = JourneyNode | ProcessNode;
type LayoutEdge = { source: string; target: string };

// Condition and terminal nodes keep fixed dimensions, but a step's width and height are worked out per
// node from its own title (see node-sizing.ts), rather than every step sharing one fixed size that
// wastes space for a short title and clips a long one. These sizes match the shapes drawn in
// ConditionNode.svelte and TerminalNode.svelte, since edges anchor to these dimensions: a 40px diamond
// for a decision, a 40px circle for a start or end.
const conditionAndTerminalDimensions = {
	condition: { width: 40, height: 40 },
	terminal: { width: 40, height: 40 }
} as const;

// Horizontal gap between two nodes sharing a rank, vertical gap between one rank and the next, and the
// blank border kept around the whole graph. Tuned so branches stay legible in the narrow graph column.
const NODE_GAP = 50;
const RANK_GAP = 60;
const MARGIN = 30;

/**
 * Returns the width and height this node occupies, so a step's dynamic dimensions and every other node's
 * fixed dimensions are looked up the same way. Exported because the graph component reuses it to work out
 * where each edge should meet a node.
 */
export function nodeSize(node: LayoutNode): { width: number; height: number } {
	if (node.type === 'step') {
		return { width: node.data.width, height: node.data.height };
	}
	return conditionAndTerminalDimensions[node.type];
}

/**
 * Positions a graph from top to bottom, handing the hard part, ranking, ordering ranks to minimise edge
 * crossings, and breaking any cycle so a journey that loops back on itself still lays out, over to dagre.
 * That is a well tested implementation of the same problem our own node and edge shapes describe, rather
 * than one this project would otherwise have to write and maintain from scratch. Dagre has no dependency
 * on rendering or dragging, it only computes positions, so this stays a pure function: it builds a fresh
 * graph from its arguments on every call and never mutates the nodes or edges it is given.
 */
export function layoutJourneyGraph<Node extends LayoutNode>(
	nodes: Node[],
	edges: LayoutEdge[]
): { nodes: Node[]; width: number; height: number } {
	const graph = new dagre.graphlib.Graph();
	// Dagre requires an edge label factory even though the graph does not attach layout metadata to connections.
	graph.setDefaultEdgeLabel(() => ({}));
	graph.setGraph({ rankdir: 'TB', nodesep: NODE_GAP, ranksep: RANK_GAP, marginx: MARGIN, marginy: MARGIN });

	for (const node of nodes) {
		// Spread into a fresh object for every node, including nodes of the same type that would otherwise
		// share the one constant object from conditionAndTerminalDimensions, because dagre adds the
		// computed position directly onto the object it is given, and two nodes sharing that object would
		// end up with the same position.
		graph.setNode(node.id, { ...nodeSize(node) });
	}

	for (const edge of edges) {
		graph.setEdge(edge.source, edge.target);
	}

	// Run layout after every node and connection is registered, since dagre ranks and orders the complete
	// graph in one pass rather than incrementally.
	dagre.layout(graph);

	const positionedNodes = nodes.map((node) => {
		const { width, height } = nodeSize(node);
		const centre = graph.node(node.id);

		// Convert dagre's centre coordinates to the top left coordinates Svelte Flow positions nodes by.
		// width/height are set here too, alongside data.width/height, since Svelte Flow uses the node's own
		// top level fields for handle placement and the connection line, not the data object's copy.
		return {
			...node,
			position: { x: centre.x - width / 2, y: centre.y - height / 2 },
			width,
			height
		};
	});

	// Dagre orders nodes within a rank purely to minimise edge crossings, with no notion of which branch
	// "comes first": a gateway's own routes can just as easily land with the later step on the left as on
	// the right. Putting those routes back in the original step order, within the space dagre gave them,
	// makes left to right on the canvas match the step numbers without changing the spacing.
	reorderBranchSiblings(positionedNodes, edges);

	const graphSize = graph.graph();

	return {
		nodes: positionedNodes,
		width: graphSize.width ?? 0,
		height: graphSize.height ?? 0
	};
}

/**
 * For every node with more than one outgoing edge (a gateway's branch routes), puts the targets in the
 * same left to right order as they appear in the input. The targets keep the space dagre gave them as a
 * group: the left most one still starts where it did, and the gaps between neighbours are kept, so boxes
 * of different widths cannot end up on top of each other. Mutates the positioned nodes in place, since it
 * only ever moves a node sideways within its own rank.
 */
function reorderBranchSiblings<Node extends LayoutNode>(positionedNodes: Node[], edges: LayoutEdge[]): void {
	const orderIndex = new Map(positionedNodes.map((node, index) => [node.id, index]));
	const nodeById = new Map(positionedNodes.map((node) => [node.id, node]));

	// A set is used because two routes can lead to the same target, such as an error route and a normal
	// route to one end state, and a node must only be placed once.
	const childrenBySource = new Map<string, Set<string>>();
	for (const edge of edges) {
		const targets = childrenBySource.get(edge.source);
		if (targets) {
			targets.add(edge.target);
		} else {
			childrenBySource.set(edge.source, new Set([edge.target]));
		}
	}

	// Nodes on the same rank share a centre line, so comparing centres works even when their heights differ.
	const centreY = (node: Node) => node.position.y + nodeSize(node).height / 2;

	for (const childIds of childrenBySource.values()) {
		if (childIds.size < 2) continue;
		const children = [...childIds].map((id) => nodeById.get(id)).filter((node): node is Node => !!node);
		if (children.length < 2) continue;

		// Only ever moves nodes dagre already placed on the same rank: anything else sharing one source but
		// landing elsewhere is left exactly where dagre put it.
		const rankCentre = centreY(children[0]);
		if (!children.every((child) => Math.abs(centreY(child) - rankCentre) < 0.5)) continue;

		// The targets as dagre placed them from left to right, and the gap it left after each one.
		const placed = [...children].sort((a, b) => a.position.x - b.position.x);
		const gaps = placed.slice(1).map((node, index) => node.position.x - (placed[index].position.x + nodeSize(placed[index]).width));

		// Another node of the same rank between the targets would be overlapped by the move, so the
		// order dagre chose is kept in that case.
		const left = placed[0].position.x;
		const right = placed[placed.length - 1].position.x + nodeSize(placed[placed.length - 1]).width;
		const blocked = positionedNodes.some(
			(other) =>
				!childIds.has(other.id) &&
				Math.abs(centreY(other) - rankCentre) < 0.5 &&
				other.position.x < right &&
				other.position.x + nodeSize(other).width > left
		);
		if (blocked) continue;

		const inStepOrder = [...children].sort((a, b) => (orderIndex.get(a.id) ?? 0) - (orderIndex.get(b.id) ?? 0));

		let nextLeft = left;
		inStepOrder.forEach((child, index) => {
			child.position = { ...child.position, x: nextLeft };
			nextLeft += nodeSize(child).width + (gaps[index] ?? 0);
		});
	}
}
