import dagre from '@dagrejs/dagre';
import type { JourneyEdge, JourneyNode } from './types';

// Condition and terminal nodes keep fixed dimensions, but a step's width and height are worked out per
// node from its own title and description (see build-journey-graph.ts), rather than every step sharing
// one fixed size that wastes space for short content and clips long content.
const conditionAndTerminalDimensions = {
	condition: { width: 240, height: 140 },
	terminal: { width: 112, height: 42 }
} as const;

/**
 * Returns the width and height Dagre should reserve for this node, so a step's dynamic dimensions and
 * every other node's fixed dimensions are looked up the same way.
 */
function getNodeDimensions(node: JourneyNode): { width: number; height: number } {
	if (node.type === 'step') {
		return { width: node.data.width, height: node.data.height };
	}
	return conditionAndTerminalDimensions[node.type];
}

/**
 * Positions a graph from top to bottom so branches remain legible without storing layout data in the fixture.
 */
export function layoutJourneyGraph(nodes: JourneyNode[], edges: JourneyEdge[]): JourneyNode[] {
	const graph = new dagre.graphlib.Graph();
	// Dagre requires an edge label factory even though the graph does not attach layout metadata to connections.
	graph.setDefaultEdgeLabel(() => ({}));
	graph.setGraph({ rankdir: 'TB', nodesep: 50, ranksep: 60, marginx: 30, marginy: 30 });

	for (const node of nodes) {
		// Spread into a fresh object for every node, including nodes of the same type that would
		// otherwise share the one constant object, because Dagre adds calculated values directly onto
		// the object it is given and two nodes sharing that object end up with the same computed position.
		graph.setNode(node.id, { ...getNodeDimensions(node) });
	}

	for (const edge of edges) {
		graph.setEdge(edge.source, edge.target);
	}

	// Run layout after every node and connection is registered because Dagre ranks the complete graph.
	dagre.layout(graph);

	return nodes.map((node) => {
		const dimensions = getNodeDimensions(node);
		const position = graph.node(node.id);

		// Convert Dagre centre coordinates to the top left coordinates expected by Svelte Flow.
		return {
			...node,
			position: {
				x: position.x - dimensions.width / 2,
				y: position.y - dimensions.height / 2
			}
		};
	});
}
