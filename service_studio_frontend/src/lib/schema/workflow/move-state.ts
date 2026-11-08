import { redirectRoutes, routesInto } from './edit-process';
import { hasNext } from './edit-state';
import type { WorkingProcess } from './working-process';

/*
	Moving a step up or down changes the journey itself. The steps are not kept in a list, so there is no
	list to reorder: a step moves by swapping places with the step it continues to, which rewires the routes
	around the pair. The step numbers follow the routes, so they change by themselves.

	1. Only two steps that each continue to a single next step can swap, so the swap never has to decide
	   what happens to the rules of a decision or to an end.
	2. The step that comes second must be reached only from the step before it. If something else also
	   leads to it, that is a point where two paths join, and swapping would change where the other path goes.
*/

/**
 * Finds the step that a step would swap places with if it moved down, which is the step it continues to.
 * Returns nothing when the swap is not allowed, so one check serves both the button and the move itself.
 */
function laterNeighbour(process: WorkingProcess, code: string): string | undefined {
	const state = process.states[code];
	// A step with nothing after it has no neighbour to swap with.
	if (!state || !hasNext(state) || state.next === undefined) return undefined;

	const neighbourCode = state.next;
	const neighbour = process.states[neighbourCode];
	// The neighbour must be a different step that also continues to a single next step, and not back to this one.
	if (!neighbour || neighbourCode === code || !hasNext(neighbour) || neighbour.next === undefined || neighbour.next === code) {
		return undefined;
	}

	// Only this step may lead to the neighbour. The start of the process counts as something leading to it.
	const into = routesInto(process, neighbourCode);
	if (into.length !== 1 || into[0].source !== code || process.start === neighbourCode) return undefined;

	return neighbourCode;
}

/**
 * Finds the step that a step would swap places with if it moved up, which is the step that leads to it.
 * Returns nothing when the swap is not allowed.
 */
function earlierNeighbour(process: WorkingProcess, code: string): string | undefined {
	// The step must have exactly one way in, and it must not be the start of the process.
	const into = routesInto(process, code);
	if (into.length !== 1 || process.start === code) return undefined;

	const earlier = into[0].source;
	return laterNeighbour(process, earlier) === code ? earlier : undefined;
}

/**
 * Tells whether a step can move down, so the panel only offers a button that will work.
 */
export function canMoveLater(process: WorkingProcess, code: string): boolean {
	return laterNeighbour(process, code) !== undefined;
}

/**
 * Tells whether a step can move up, so the panel only offers a button that will work.
 */
export function canMoveEarlier(process: WorkingProcess, code: string): boolean {
	return earlierNeighbour(process, code) !== undefined;
}

/**
 * Returns a copy of the process in which a step has swapped places with the step after it. Everything that
 * led to the step now leads to its neighbour, the neighbour continues to the step, and the step continues
 * to where the neighbour went. If the swap is not allowed the process is returned as it is.
 */
export function moveLater(process: WorkingProcess, code: string): WorkingProcess {
	const neighbourCode = laterNeighbour(process, code);
	if (!neighbourCode) return process;

	// Both steps are read before anything is redirected, because the swap rebuilds them from these copies.
	const state = process.states[code];
	const neighbour = process.states[neighbourCode];
	if (!hasNext(state) || !hasNext(neighbour) || neighbour.next === undefined) return process;

	// Everything that led to the step, including the start of the process, now leads to the neighbour.
	const redirected = redirectRoutes(process, code, neighbourCode);

	return {
		...redirected,
		states: {
			...redirected.states,
			// The neighbour comes first and continues to the step, and its other routes are left as they were.
			[neighbourCode]: { ...neighbour, next: code },
			// The step comes second and continues to wherever the neighbour used to go.
			[code]: { ...state, next: neighbour.next }
		}
	};
}

/**
 * Returns a copy of the process in which a step has swapped places with the step before it. This is the
 * earlier step moving down, so it uses the same swap. If the swap is not allowed the process is returned
 * as it is.
 */
export function moveEarlier(process: WorkingProcess, code: string): WorkingProcess {
	const earlier = earlierNeighbour(process, code);
	return earlier ? moveLater(process, earlier) : process;
}
