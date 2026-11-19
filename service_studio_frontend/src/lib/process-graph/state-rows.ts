import type { State } from '$lib/schema/workflow/process';
import type { ProcessNode } from './process-graph-types';

/**
 * One line of the list of steps beside the graph. It carries the number and the title, which are the same as
 * the numbered box on the graph, and the kind of state, so an editor can choose to show a tag for it.
 */
export type StateRow = {
	stateId: string;
	title: string;
	number: number;
	stateType: State['state_type'];
};

/**
 * Turns the graph's nodes into the rows of the list, in the same order as the graph so the numbers
 * match. Only the numbered boxes are listed. A decision diamond, an end dot and a developer step are not
 * steps, so they are left out of the list and out of the count, and are chosen on the graph itself.
 * Reading the nodes and not the process keeps the list and the graph from disagreeing about a title or
 * a number.
 */
export function stateRows(nodes: ProcessNode[]): StateRow[] {
	return nodes.flatMap((node): StateRow[] =>
		node.type === 'step' && node.data.stepNumber !== undefined
			? [{ stateId: node.data.stateId, title: node.data.title, number: node.data.stepNumber, stateType: node.data.stateType }]
			: []
	);
}

/**
 * One state that a route can lead to, with the words that name it in a list of choices.
 */
export type TargetOption = { stateId: string; label: string };

/**
 * Lists every state that a route could lead to, in graph order, for a list of choices. A box is named by its
 * number and title, so two boxes with the same title can still be told apart, and a diamond or an end dot is
 * named by its shape and title. The start dot is left out because nothing leads back to it. Codes are not
 * shown, because they are for the schema and not for the person.
 */
export function targetOptions(nodes: ProcessNode[]): TargetOption[] {
	return nodes.flatMap((node): TargetOption[] => {
		switch (node.type) {
			case 'step':
				// A developer step has no number, so it is named by its title alone.
				return [{ stateId: node.data.stateId, label: node.data.stepNumber === undefined ? node.data.title : `${node.data.stepNumber}. ${node.data.title}` }];
			case 'condition':
				return [{ stateId: node.data.stateId, label: `Decision: ${node.data.title}` }];
			case 'terminal':
				return node.data.stateId ? [{ stateId: node.data.stateId, label: `End: ${node.data.title ?? node.data.label}` }] : [];
		}
	});
}
