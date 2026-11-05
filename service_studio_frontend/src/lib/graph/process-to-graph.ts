import { journeyOrder } from '$lib/schema/workflow/journey-order';
import type { Process, State } from '$lib/schema/workflow/process';
import { isErrorKind, routesOf } from '$lib/schema/workflow/routes';
import { estimateStepNodeHeight, estimateStepNodeWidth } from './node-sizing';
import type { ProcessEdge, ProcessEdgeData, ProcessGraphElements, ProcessNode } from './process-graph-types';
import { tidyCode } from './tidy-code';

// A placeholder coordinate every node is created with. The layout replaces it, so this value is only
// ever seen before the layout runs.
const initialPosition = { x: 0, y: 0 };

// The id of the start dot. State names are chosen by the workflow author, so this is written so that
// it will not be mistaken for one.
export const startNodeId = '__start__';

/**
 * Tells whether an edge is an error route. The graph hides these by default, because several steps
 * often lead to the same few end states and the lines cross the main journey, so the journey is
 * easier to read without them.
 */
export function isErrorRoute(edge: ProcessEdge): boolean {
	return edge.data !== undefined && isErrorKind(edge.data.kind);
}

/**
 * Finds every node that can be reached from the start dot by following the given edges. The walk is
 * used to tell the main journey from the states that only an error route leads to.
 */
function reachableNodes(edges: ProcessEdge[]): Set<string> {
	const reached = new Set<string>([startNodeId]);
	const queue = [startNodeId];

	while (queue.length) {
		const node = queue.shift()!;
		for (const edge of edges) {
			if (edge.source === node && !reached.has(edge.target)) {
				reached.add(edge.target);
				queue.push(edge.target);
			}
		}
	}

	return reached;
}

/**
 * Returns the part of a graph that is shown. With error routes on this is the whole graph. With them
 * off, the error routes are removed and so is every state that only an error route leads to, such as
 * an end dot that nothing else reaches, because it would otherwise float on its own. A state that
 * nothing leads to at all is kept, because that is a problem the person should see.
 */
export function visibleGraph(graph: ProcessGraphElements, showErrorRoutes: boolean): ProcessGraphElements {
	if (showErrorRoutes) return graph;

	const mainEdges = graph.edges.filter((edge) => !isErrorRoute(edge));
	const reachedWithErrorRoutes = reachableNodes(graph.edges);
	const reachedOnMainJourney = reachableNodes(mainEdges);
	const nodes = graph.nodes.filter((node) => !reachedWithErrorRoutes.has(node.id) || reachedOnMainJourney.has(node.id));
	const shown = new Set(nodes.map((node) => node.id));

	return { nodes, edges: mainEdges.filter((edge) => shown.has(edge.source) && shown.has(edge.target)) };
}

/**
 * Gives every route into a shared end state its own end dot, drawn just below the step the route leaves
 * from. An end state that many steps lead to would otherwise be one dot with long lines running to it from
 * far away, and it can look as though it belongs to a step it is not under. Each copy stands for the same
 * end state and carries the same state id, so choosing any of them selects the state. An end state with one
 * route into it, or none, is left alone.
 */
export function separateEndDots(graph: ProcessGraphElements): ProcessGraphElements {
	const routesInto = new Map<string, ProcessEdge[]>();
	for (const edge of graph.edges) routesInto.set(edge.target, [...(routesInto.get(edge.target) ?? []), edge]);

	const isShared = (node: ProcessNode) =>
		node.type === 'terminal' && node.data.appearance === 'end' && (routesInto.get(node.id)?.length ?? 0) > 1;

	// A copy is named after the end state and the step it sits under. Two routes from one step to the same
	// end state, such as a next route and an error route, share one dot.
	const copyId = (endId: string, source: string) => `${endId}#${source}`;

	const nodes = graph.nodes.flatMap((node): ProcessNode[] => {
		if (!isShared(node)) return [node];
		const sources = [...new Set(routesInto.get(node.id)!.map((edge) => edge.source))];
		return sources.map((source) => ({ ...node, id: copyId(node.id, source) }));
	});
	const sharedIds = new Set(graph.nodes.filter(isShared).map((node) => node.id));
	const edges = graph.edges.map((edge) =>
		sharedIds.has(edge.target) ? { ...edge, target: copyId(edge.target, edge.source) } : edge
	);

	return { nodes, edges };
}

/**
 * Describes the shape of a graph as text: which boxes there are and which lines join them. Two graphs with
 * the same description have the same shape even if a title is different, so the page can keep the boxes
 * where they are when a step is only renamed, and arrange the graph again only when a box or a line is
 * added, removed or moved to a different place.
 */
export function graphShape(graph: ProcessGraphElements): string {
	const nodes = graph.nodes.map((node) => node.id).join(',');
	const edges = graph.edges.map((edge) => `${edge.source}>${edge.target}`).join(',');
	return `${nodes}|${edges}`;
}

/**
 * Counts the numbered boxes in a graph. This is the number of steps in a process. A decision diamond and
 * an end dot are not counted, so the count matches the last number on the graph and the length of the
 * list of steps.
 */
export function stepCount(graph: ProcessGraphElements): number {
	return graph.nodes.filter((node) => node.type === 'step').length;
}

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
export function stateTitle(state: State, code: string): string {
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
					title,
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
			// An invoke state shows a second line that opens the process it runs, so its box is taller.
			const opensProcess =
				state.type === 'invoke' ? { id: state.process, title: tidyCode(state.process) } : undefined;

			nodes.push({
				id: code,
				type: 'step',
				position: initialPosition,
				data: {
					stateId: code,
					stepNumber,
					title,
					stateType: state.type,
					opensProcess,
					width,
					height: estimateStepNodeHeight(`${stepNumber}. ${title}`, width, opensProcess ? 1 : 0),
					ariaLabel: opensProcess
						? `Step ${stepNumber}, ${title}, opens the ${opensProcess.title} process`
						: `Step ${stepNumber}, ${title}`
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
