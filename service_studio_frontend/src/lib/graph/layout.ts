import type { JourneyEdge, JourneyNode } from './types';

// Condition and terminal nodes keep fixed dimensions, but a step's width and height are worked out per
// node from its own title and description (see build-journey-graph.ts), rather than every step sharing
// one fixed size that wastes space for short content and clips long content.
const conditionAndTerminalDimensions = {
	condition: { width: 240, height: 140 },
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
 * Positions a graph from top to bottom in horizontal ranks, so branches stay legible without any layout
 * data being stored in the fixture. Pure: it returns fresh node objects with a new position and never
 * mutates its input, so it is safe to re-run whenever the steps or branching toggle change.
 */
export function layoutJourneyGraph(
	nodes: JourneyNode[],
	edges: JourneyEdge[]
): { nodes: JourneyNode[]; width: number; height: number } {
	// Build the forward adjacency and the incoming edge count for every node, the two things Kahn's
	// algorithm needs to walk the graph in dependency order.
	const successors = new Map<string, string[]>();
	const indegree = new Map<string, number>();
	for (const node of nodes) {
		successors.set(node.id, []);
		indegree.set(node.id, 0);
	}
	for (const edge of edges) {
		successors.get(edge.source)?.push(edge.target);
		indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
	}

	// Longest path ranking by Kahn's algorithm: start every node with no incoming edge at rank 0, then
	// push each node to one rank past the furthest predecessor that reaches it.
	const rank = new Map<string, number>();
	const queue: string[] = [];
	for (const node of nodes) {
		if ((indegree.get(node.id) ?? 0) === 0) {
			rank.set(node.id, 0);
			queue.push(node.id);
		}
	}
	while (queue.length > 0) {
		const current = queue.shift() as string;
		const currentRank = rank.get(current) ?? 0;
		for (const next of successors.get(current) ?? []) {
			rank.set(next, Math.max(rank.get(next) ?? 0, currentRank + 1));
			const remaining = (indegree.get(next) ?? 0) - 1;
			indegree.set(next, remaining);
			if (remaining === 0) {
				queue.push(next);
			}
		}
	}
	// Any node the walk never reached is part of a cycle. createJourneyGraph cannot currently produce
	// one, so this only matters if a real branching schema later introduces cycles: dropping those nodes
	// to rank 0 keeps the graph drawing something visible rather than throwing.
	for (const node of nodes) {
		if (!rank.has(node.id)) {
			rank.set(node.id, 0);
		}
	}

	// Group node ids by rank, keeping the original array order within each rank. The build order
	// (start, end, step-1..n, condition) already places the left branch step before the right one, so no
	// crossing reduction pass is needed for the single fork this demo produces. Add a barycentre ordering
	// pass here if a real multi-branch schema ever arrives.
	const ranks: JourneyNode[][] = [];
	for (const node of nodes) {
		const r = rank.get(node.id) ?? 0;
		(ranks[r] ??= []).push(node);
	}

	// Work out how much space each rank needs: its tallest node sets the row height, and its nodes plus
	// the gaps between them set the row width. The widest row then decides the graph width every row is
	// centred within.
	const rankHeights = ranks.map((rankNodes) => Math.max(...rankNodes.map((node) => nodeSize(node).height)));
	const rankWidths = ranks.map(
		(rankNodes) =>
			rankNodes.reduce((total, node) => total + nodeSize(node).width, 0) + NODE_GAP * (rankNodes.length - 1)
	);
	const maxRankWidth = Math.max(...rankWidths);

	// Place every node: walk the ranks top to bottom keeping a running vertical offset, and within each
	// rank walk left to right keeping a running horizontal offset from that rank's centred start.
	const positionById = new Map<string, { x: number; y: number }>();
	let top = MARGIN;
	ranks.forEach((rankNodes, r) => {
		let x = MARGIN + (maxRankWidth - rankWidths[r]) / 2;
		for (const node of rankNodes) {
			const { width, height } = nodeSize(node);
			positionById.set(node.id, { x, y: top + (rankHeights[r] - height) / 2 });
			x += width + NODE_GAP;
		}
		top += rankHeights[r] + RANK_GAP;
	});

	return {
		nodes: nodes.map((node) => ({
			...node,
			position: positionById.get(node.id) ?? { x: MARGIN, y: MARGIN }
		})),
		width: MARGIN * 2 + maxRankWidth,
		// top has one trailing RANK_GAP added past the last rank, so remove it and add the bottom margin.
		height: top - RANK_GAP + MARGIN
	};
}
