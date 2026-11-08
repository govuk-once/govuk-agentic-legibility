import type { WorkingProcess } from './working-process';
import { isErrorKind, routesOf, type Route } from './routes';

/*
	A process stores its states as a map, which has no meaningful order. The journey order is worked
	out by following routes from the start state instead, so step numbers always match what the
	person would meet first, and reordering a step changes its number by changing its routes.
*/

/**
 * Lists the states that can be reached from the start state, nearest first. The walk goes across
 * the journey one step at a time, so every state one route from the start comes before any state
 * two routes away. That matches the top to bottom rows of the graph, and a state that two branches
 * rejoin at is numbered after both branches. Within one step the routes are followed in the order
 * they are written, so a choice's rules come before its default.
 *
 * A route to a state that does not exist is skipped, so the order can still be worked out while an
 * edit has left the process half finished. A caller can pass a test to follow only some routes, for
 * example to leave out the error routes.
 */
export function reachableInOrder(process: WorkingProcess, followRoute: (route: Route) => boolean = () => true): string[] {
	const order: string[] = [];
	const seen = new Set<string>();
	const queue = [process.start];

	while (queue.length) {
		const name = queue.shift()!;
		if (seen.has(name) || !(name in process.states)) continue;

		seen.add(name);
		order.push(name);
		queue.push(...routesOf(process.states[name]).filter(followRoute).map((route) => route.target));
	}

	return order;
}

/**
 * Lists every state of a process in journey order. The states on the main journey come first, which
 * leaves out the error routes. Then come the states that only an error route reaches, then any state
 * that nothing leads to, in the order the process file lists them, so a state left behind still
 * appears instead of vanishing from the graph. Putting the main journey first means the steps that
 * are shown when error routes are hidden are numbered one after another with no gaps.
 */
export function journeyOrder(process: WorkingProcess): string[] {
	const ordered = [
		...reachableInOrder(process, (route) => !isErrorKind(route.kind)),
		...reachableInOrder(process),
		...Object.keys(process.states)
	];

	return [...new Set(ordered)];
}
