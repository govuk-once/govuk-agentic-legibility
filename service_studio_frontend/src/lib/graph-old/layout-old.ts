import { layoutJourneyGraph as layoutPlainGraph } from '../graph-kit/layout';
import type { JourneyEdge, JourneyNode } from './types';

/*
	How the original graph arranges its boxes. The plain layout in graph-kit places every box with dagre,
	and the step here then puts a decision's branches into the order of the steps. It is kept with the
	original graph, which is deleted when the old editor is, so the shared layout stays free of it.
*/

/**
 * Positions the original graph from top to bottom and then puts each decision's branches in step order.
 */
export function layoutJourneyGraph(
	nodes: JourneyNode[],
	edges: JourneyEdge[]
): { nodes: JourneyNode[]; width: number; height: number } {
	const laidOut = layoutPlainGraph(nodes, edges);

	// Dagre orders nodes within a rank purely to minimise edge crossings, with no notion of which branch
	// "comes first": a gateway's own routes can just as easily land with the later step on the left as on
	// the right. Reassigning the same set of x positions dagre already chose, in the original step order
	// instead, keeps its spacing while making left to right on the canvas match the step numbers.
	reorderBranchSiblings(laidOut.nodes, edges);

	return laidOut;
}

/**
 * For every node with more than one outgoing edge (a gateway's branch routes), sorts those targets into
 * the same order they appear in the input, then hands out dagre's own x positions for that rank to them
 * in that order. Mutates the positioned nodes in place, since it only ever reassigns an x each node
 * already has from dagre, never its rank or the set of positions available within it.
 */
function reorderBranchSiblings(positionedNodes: JourneyNode[], edges: JourneyEdge[]): void {
	const orderIndex = new Map(positionedNodes.map((node, index) => [node.id, index]));
	const nodeById = new Map(positionedNodes.map((node) => [node.id, node]));

	const childrenBySource = new Map<string, string[]>();
	for (const edge of edges) {
		const list = childrenBySource.get(edge.source);
		if (list) {
			list.push(edge.target);
		} else {
			childrenBySource.set(edge.source, [edge.target]);
		}
	}

	for (const childIds of childrenBySource.values()) {
		if (childIds.length < 2) continue;
		const children = childIds.map((id) => nodeById.get(id)).filter((node): node is JourneyNode => !!node);
		if (children.length < 2) continue;

		// Only ever reassigns positions among nodes dagre already placed on the same rank: anything else
		// sharing one source but landing elsewhere, which does not happen for a gateway's own routes but
		// could for a step with an unrelated pair of edges, is left exactly where dagre put it.
		const rankY = children[0].position.y;
		if (!children.every((child) => Math.abs(child.position.y - rankY) < 0.5)) continue;

		const slots = children.map((child) => child.position.x).sort((a, b) => a - b);
		const inStepOrder = [...children].sort(
			(a, b) => (orderIndex.get(a.id) ?? 0) - (orderIndex.get(b.id) ?? 0)
		);

		inStepOrder.forEach((child, index) => {
			child.position = { ...child.position, x: slots[index] };
		});
	}
}
