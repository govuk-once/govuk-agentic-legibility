import { journeyOrder } from '$lib/schema/workflow/journey-order';
import type { Process, State } from '$lib/schema/workflow/process';
import { routesOf } from '$lib/schema/workflow/routes';
import { estimateStepNodeHeight, estimateStepNodeWidth } from './node-sizing';
import type { ProcessEdge, ProcessGraphElements, ProcessNode } from './process-graph-types';
import { tidyCode } from './tidy-code';

// A placeholder coordinate every node is created with. The layout replaces it, so this value is only
// ever seen before the layout runs.
const initialPosition = { x: 0, y: 0 };

// The id of the start dot. State names are chosen by the workflow author, so this is written so that
// it will not be mistaken for one.
export const startNodeId = '__start__';

/**
 * Returns the words a state already carries that make a good title: the question an input asks, the
 * message an output says, or the outcome of an end. A state with none of these, such as a call, has
 * no text of its own.
 */
function stateText(state: State): string | undefined {
	switch (state.type) {
		case 'input':
			return state.prompt;
		case 'output':
			return state.message;
		case 'end':
			return state.outcome ? tidyCode(state.outcome) : undefined;
		default:
			return undefined;
	}
}

/**
 * Chooses the title shown for a state. A title written by the author comes first, then the state's
 * own text, then its code tidied into words, so every state has something readable to show.
 */
function stateTitle(state: State, code: string): string {
	return state.name ?? stateText(state) ?? tidyCode(code);
}

/**
 * Turns one process into the nodes and edges the graph draws. Each state becomes one node: a choice
 * is a diamond, an end is a dot, and every other state is a numbered box. Nodes are listed in journey
 * order and boxes are numbered in that order, so the numbers follow the routes from the start and a
 * state that nothing leads to comes last. A route to a state that does not exist draws no edge, so the
 * graph still builds while an edit has left the process half finished.
 */
export function processToGraph(process: Process): ProcessGraphElements {
	const nodes: ProcessNode[] = [
		{
			id: startNodeId,
			type: 'terminal',
			position: initialPosition,
			data: { label: 'Start', appearance: 'start', ariaLabel: 'Journey start' }
		}
	];
	const edges: ProcessEdge[] = [];
	const order = journeyOrder(process);
	let stepNumber = 0;

	for (const code of order) {
		const state = process.states[code];
		const title = stateTitle(state, code);

		if (state.type === 'end') {
			nodes.push({
				id: code,
				type: 'terminal',
				position: initialPosition,
				data: {
					label: 'End',
					appearance: 'end',
					ariaLabel: `Journey end, ${title}`,
					stateId: code,
					status: state.status
				}
			});
		} else if (state.type === 'choice') {
			nodes.push({
				id: code,
				type: 'condition',
				position: initialPosition,
				data: { stateId: code, title, ariaLabel: `Decision, ${title}` }
			});
		} else {
			stepNumber += 1;
			const width = estimateStepNodeWidth(`${stepNumber}. ${title}`);

			nodes.push({
				id: code,
				type: 'step',
				position: initialPosition,
				data: {
					stateId: code,
					stepNumber,
					title,
					stateType: state.type,
					width,
					height: estimateStepNodeHeight(`${stepNumber}. ${title}`, width),
					ariaLabel: `Step ${stepNumber}, ${title}`
				}
			});
		}
	}

	if (process.start in process.states) {
		edges.push({ id: `${startNodeId}:start`, source: startNodeId, target: process.start, data: { kind: 'start' } });
	}

	for (const code of order) {
		for (const route of routesOf(process.states[code])) {
			if (!(route.target in process.states)) continue;

			// The path inside the state makes the id unique even when two routes lead to the same target.
			edges.push({
				id: `${code}:${route.path.join('.')}`,
				source: code,
				target: route.target,
				data: { kind: route.kind }
			});
		}
	}

	return { nodes, edges };
}
