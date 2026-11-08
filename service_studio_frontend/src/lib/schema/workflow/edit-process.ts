import type { WorkingProcess, WorkingState } from './working-process';
import { routesOf, withRouteTarget, type Route } from './routes';

/*
	The changes the editor makes to the routes of a whole process, written as plain functions that take a
	process and return a changed copy. Like the state changes in edit-state.ts, nothing here changes what it
	is given and nothing here checks the result, because the whole journey is checked once, before it is passed on.
*/

/**
 * One route that leads into a state: the state it leaves from, and the route itself.
 */
export type IncomingRoute = { source: string; route: Route };

/**
 * Lists every route that leads into a state, from every state of the process. The start of the process is
 * not a route, so a caller that cares whether the state is the start checks process.start as well.
 */
export function routesInto(process: WorkingProcess, code: string): IncomingRoute[] {
	return Object.entries(process.states).flatMap(([source, state]) =>
		routesOf(state)
			.filter((route) => route.target === code)
			.map((route) => ({ source, route }))
	);
}

/**
 * Returns a copy of the process in which everything that led to one state leads to another instead. That
 * covers every kind of route and the start of the process, so a state can be taken out of the journey
 * without leaving anything pointing at it.
 */
export function redirectRoutes(process: WorkingProcess, from: string, to: string): WorkingProcess {
	const states = Object.fromEntries(
		Object.entries(process.states).map(([code, state]) => {
			// Each route into the old state is pointed at the new one. A state with no such route comes out unchanged.
			const redirected = routesOf(state)
				.filter((route) => route.target === from)
				.reduce((current, route) => withRouteTarget(current, route.path, to), state);
			return [code, redirected];
		})
	);

	return { ...process, start: process.start === from ? to : process.start, states };
}

/**
 * Chooses a name for a new state that no state in the process already has. The base is used as it is when it
 * is free, and otherwise a number is added to it, so a second new step is called new_step_2 and a third
 * new_step_3.
 */
export function uniqueStateCode(process: WorkingProcess, base: string): string {
	if (!(base in process.states)) return base;

	// Count up from two until a free name is found.
	let number = 2;
	while (`${base}_${number}` in process.states) number += 1;
	return `${base}_${number}`;
}

/**
 * Takes out every state that has been left with nothing leading to it, starting from the states given. A state
 * is only taken out when nothing in the process still leads to it and it is not the start, and then whatever
 * it led to is checked in the same way. Ending a branch therefore never leaves a chain of steps behind that
 * nothing reaches any more, and a state that something else still leads to is left alone.
 */
export function removeUnreachableStates(process: WorkingProcess, roots: string[]): WorkingProcess {
	let states = process.states;
	const toCheck = [...roots];

	while (toCheck.length > 0) {
		const code = toCheck.pop()!;
		if (code === process.start || !(code in states)) continue;

		// Something that still leads here keeps it.
		const stillLedTo = Object.values(states).some((state) => routesOf(state).some((route) => route.target === code));
		if (stillLedTo) continue;

		// Whatever this state led to may now be on its own as well, so it is checked next.
		toCheck.push(...routesOf(states[code]).map((route) => route.target));
		const { [code]: _taken, ...rest } = states;
		states = rest;
	}

	return states === process.states ? process : { ...process, states };
}

/**
 * Returns a copy of the process that begins at a different state. The state it began at is left where it
 * is, with nothing leading to it unless some other route does.
 */
export function setStart(process: WorkingProcess, code: string): WorkingProcess {
	return { ...process, start: code };
}

/**
 * Returns a copy of the process with a new state added under a name that is not yet used. The name that was
 * asked for is used as it is when it is free, and has a number added when it is not. The result carries the
 * name that was chosen.
 */
export function addState(process: WorkingProcess, base: string, state: WorkingState): { process: WorkingProcess; code: string } {
	const code = uniqueStateCode(process, base);
	return { process: { ...process, states: { ...process.states, [code]: state } }, code };
}
