import dagre from '@dagrejs/dagre';
import type { JourneyEdge, JourneyNode } from './types';

// Condition and terminal nodes keep fixed dimensions, but a step's width and height are worked out per
// node from its own title (see node-sizing.ts), rather than every step sharing one fixed size that
// wastes space for a short title and clips a long one. The condition size must match the diamond drawn
// in ConditionNode.svelte, since edges anchor to these dimensions.
const conditionAndTerminalDimensions = {
	condition: { width: 300, height: 176 },
	terminal: { width: 72, height: 72 }
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
export function nodeSize(node: JourneyNode): { width: number; height: number } {
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
export function layoutJourneyGraph(
	nodes: JourneyNode[],
	edges: JourneyEdge[]
): { nodes: JourneyNode[]; width: number; height: number } {
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

		// Convert dagre's centre coordinates to the top left coordinates the renderer positions nodes by.
		return {
			...node,
			position: { x: centre.x - width / 2, y: centre.y - height / 2 }
		};
	});

	const graphSize = graph.graph();

	return {
		nodes: positionedNodes,
		width: graphSize.width ?? 0,
		height: graphSize.height ?? 0
	};
}
