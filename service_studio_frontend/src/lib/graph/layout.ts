import dagre from '@dagrejs/dagre';
import type { JourneyEdge, JourneyNode } from './types';

// These values must match the rendered node sizes so Dagre reserves enough space and coordinate conversion remains accurate.
const nodeDimensions = {
	step: { width: 280, height: 78 },
	condition: { width: 240, height: 140 },
	terminal: { width: 112, height: 42 }
} as const;

/**
 * Positions a graph from top to bottom so branches remain legible without storing layout data in the fixture.
 */
export function layoutJourneyGraph(nodes: JourneyNode[], edges: JourneyEdge[]): JourneyNode[] {
	const graph = new dagre.graphlib.Graph();
	// Dagre requires an edge label factory even though the graph does not attach layout metadata to connections.
	graph.setDefaultEdgeLabel(() => ({}));
	graph.setGraph({ rankdir: 'TB', nodesep: 50, ranksep: 60, marginx: 30, marginy: 30 });

	for (const node of nodes) {
		const dimensions = nodeDimensions[node.type];
		// Give each node its own dimensions object because Dagre adds calculated values to the object it receives.
		graph.setNode(node.id, { ...dimensions });
	}

	for (const edge of edges) {
		graph.setEdge(edge.source, edge.target);
	}

	// Run layout after every node and connection is registered because Dagre ranks the complete graph.
	dagre.layout(graph);

	return nodes.map((node) => {
		const dimensions = nodeDimensions[node.type];
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
