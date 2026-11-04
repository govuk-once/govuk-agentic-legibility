import type { ProcessNode } from './process-graph-types';

/**
 * One line of the list of steps beside the graph. It carries only what the line shows, the number and
 * the title, which are the same as the numbered box on the graph.
 */
export type StateRow = {
	stateId: string;
	title: string;
	number: number;
};

/**
 * Turns the graph's nodes into the rows of the list, in the same order as the graph so the numbers
 * match. Only the numbered boxes are listed. A decision diamond and an end dot are shapes on the graph,
 * not steps, so they are left out of the list and out of the count, and are chosen on the graph itself.
 * Reading the nodes and not the process keeps the list and the graph from disagreeing about a title or
 * a number.
 */
export function stateRows(nodes: ProcessNode[]): StateRow[] {
	return nodes.flatMap((node): StateRow[] =>
		node.type === 'step' ? [{ stateId: node.data.stateId, title: node.data.title, number: node.data.stepNumber }] : []
	);
}
