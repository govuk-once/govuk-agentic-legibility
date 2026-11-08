import dagre from '@dagrejs/dagre';

// The layout reads only the id, the type and the size of a node, and only the two ends of an edge. Any
// editor whose boxes, diamonds and dots have these fields can use it, so it does not depend on any one
// editor's own node types.
export type LayoutNode = { id: string; position: { x: number; y: number } } & (
	| { type?: 'step'; data: { width: number; height: number } }
	| { type?: 'condition' | 'terminal' }
);
export type LayoutEdge = { source: string; target: string };

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
export const NODE_GAP = 50;
export const RANK_GAP = 60;
const MARGIN = 30;

// The dagre settings that change how a graph is arranged. Both are optional, and leaving them out keeps
// dagre's own defaults.
export type LayoutOptions = {
	// Which corner of a group of connected boxes the others line up with. A straight run of boxes then
	// stays in one column instead of drifting sideways.
	align?: 'UL' | 'UR' | 'DL' | 'DR';
	// How boxes are put into rows. See the dagre documentation for what each one favours.
	ranker?: 'network-simplex' | 'tight-tree' | 'longest-path';
};

/**
 * Returns the width and height this node occupies, so a step's dynamic dimensions and every other node's
 * fixed dimensions are looked up the same way. Exported because the graph component reuses it to work out
 * where each edge should meet a node.
 */
export function nodeSize(node: LayoutNode): { width: number; height: number } {
	if (node.type === 'step') {
		return { width: node.data.width, height: node.data.height };
	}
	return conditionAndTerminalDimensions[node.type ?? 'terminal'];
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
	edges: LayoutEdge[],
	options: LayoutOptions = {}
): { nodes: Node[]; width: number; height: number } {
	const graph = new dagre.graphlib.Graph();
	// Dagre requires an edge label factory even though the graph does not attach layout metadata to connections.
	graph.setDefaultEdgeLabel(() => ({}));
	graph.setGraph({ rankdir: 'TB', nodesep: NODE_GAP, ranksep: RANK_GAP, marginx: MARGIN, marginy: MARGIN, ...options });

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

	const graphSize = graph.graph();

	return {
		nodes: positionedNodes,
		width: graphSize.width ?? 0,
		height: graphSize.height ?? 0
	};
}
