import {
	layoutJourneyGraph,
	nodeSize,
	NODE_GAP,
	RANK_GAP,
	type LayoutEdge,
	type LayoutOptions
} from '$lib/graph-kit/layout';
import type { ProcessNode } from './process-graph-types';

/*
	How the full editor arranges the graph of one process. The plain layout in graph-kit places every box
	with dagre. The two steps here then slide boxes sideways within their row so the graph reads better.
	They live here and not in graph-kit because only this editor wants them.
*/

// The settings used for the process graph. The tight tree ranker keeps each box close to the box it
// follows, which measured about 17 percent less sideways drift on the real example processes than
// dagre's default and made no graph wider.
export const processLayoutOptions: LayoutOptions = { ranker: 'tight-tree' };

/**
 * Places every box of a process graph. Dagre decides the rows and the order of the boxes in each row so
 * that the fewest lines cross, and that order is kept. The two steps after it only slide boxes sideways
 * within their row, to sit under the box they follow. It is a pure function and returns new nodes.
 */
export function arrangeProcessGraph(
	nodes: ProcessNode[],
	edges: LayoutEdge[]
): { nodes: ProcessNode[]; width: number; height: number } {
	const laidOut = layoutJourneyGraph(nodes, edges, processLayoutOptions);

	centreBranchesUnderParents(laidOut.nodes, edges);
	centreEndDotsUnderParents(laidOut.nodes, edges);

	return laidOut;
}

/**
 * For every node with more than one outgoing edge, such as a decision, moves the boxes it leads to as a
 * group so they sit evenly to its left and right and not far to one side. The order of the boxes is the
 * order dagre chose, because dagre picks the order that crosses the fewest lines, and putting them back in
 * step order would make the lines below them cross. A group is only moved when the boxes it would pass over
 * or land beside on the same row leave a gap, so it never crowds another box. Mutates the positioned nodes
 * in place, since it only ever moves a node sideways within its own row.
 */
function centreBranchesUnderParents(positionedNodes: ProcessNode[], edges: LayoutEdge[]): void {
	const nodeById = new Map(positionedNodes.map((node) => [node.id, node]));

	// A set is used because two routes can lead to the same target, such as an error route and a normal
	// route to one end state, and a node must only be moved once.
	const childrenBySource = new Map<string, Set<string>>();
	for (const edge of edges) {
		const targets = childrenBySource.get(edge.source);
		if (targets) {
			targets.add(edge.target);
		} else {
			childrenBySource.set(edge.source, new Set([edge.target]));
		}
	}

	// Nodes on the same row share a centre line, so comparing centres works even when their heights differ.
	const centreY = (node: ProcessNode) => node.position.y + nodeSize(node).height / 2;

	for (const [sourceId, childIds] of childrenBySource) {
		const source = nodeById.get(sourceId);
		const children = [...childIds].map((id) => nodeById.get(id)).filter((node): node is ProcessNode => !!node);
		if (!source || children.length < 2) continue;

		// Only moves boxes dagre already placed on the same row: anything else sharing one source but landing
		// elsewhere is left exactly where dagre put it.
		const rowCentre = centreY(children[0]);
		if (!children.every((child) => Math.abs(centreY(child) - rowCentre) < 0.5)) continue;

		const left = Math.min(...children.map((child) => child.position.x));
		const right = Math.max(...children.map((child) => child.position.x + nodeSize(child).width));
		const shift = source.position.x + nodeSize(source).width / 2 - (left + right) / 2;

		// The whole stretch the group covers, from where it is to where it would be, with a gap each side. Any
		// other box of the row inside it would be crowded or jumped over, which changes the order of the row.
		const from = Math.min(left, left + shift) - NODE_GAP;
		const to = Math.max(right, right + shift) + NODE_GAP;
		const crowded = positionedNodes.some(
			(other) =>
				!childIds.has(other.id) &&
				Math.abs(centreY(other) - rowCentre) < 0.5 &&
				other.position.x < to &&
				other.position.x + nodeSize(other).width > from
		);
		if (!crowded) {
			for (const child of children) child.position = { ...child.position, x: child.position.x + shift };
		}
	}
}

/**
 * Puts each end dot directly under the step that leads to it. Dagre places a dot as it suits the rest of
 * the graph, which can leave it to one side or far below and make it look as though it belongs to a
 * neighbouring step. Nothing leaves an end dot, so moving it cannot disturb any other line. The dot is
 * tried first just below its step, then at the depth dagre gave it. It is only moved to a place that is
 * clear, both for the dot itself and for the line down to it, so it never lands on top of a box or hides a
 * line behind one. Mutates the positioned nodes in place.
 */
function centreEndDotsUnderParents(positionedNodes: ProcessNode[], edges: LayoutEdge[]): void {
	const nodeById = new Map(positionedNodes.map((node) => [node.id, node]));

	for (const dot of positionedNodes) {
		if (dot.type !== 'terminal' || dot.data.appearance !== 'end') continue;

		// Only a dot with exactly one line into it has a single step to sit under.
		const into = edges.filter((edge) => edge.target === dot.id);
		const parent = into.length === 1 ? nodeById.get(into[0].source) : undefined;
		if (!parent) continue;

		const { width, height } = nodeSize(dot);
		const left = parent.position.x + nodeSize(parent).width / 2 - width / 2;
		const parentBottom = parent.position.y + nodeSize(parent).height;

		// Whether any other box is in the columns of the dot, between the bottom of the step and the bottom
		// of a dot placed at the given height. That covers the dot and the line down to it.
		const isClear = (top: number) =>
			!positionedNodes.some(
				(other) =>
					other !== dot &&
					other !== parent &&
					other.position.x < left + width + NODE_GAP / 2 &&
					other.position.x + nodeSize(other).width > left - NODE_GAP / 2 &&
					other.position.y < top + height &&
					other.position.y + nodeSize(other).height > parentBottom
			);

		const justBelow = parentBottom + RANK_GAP;
		const place = [justBelow, dot.position.y].find((top) => top >= justBelow - 0.5 && isClear(top));
		if (place !== undefined) dot.position = { x: left, y: place };
	}
}
