import { routesInto } from '$lib/schema/workflow/edit-process';
import type { EditResult } from '$lib/schema/workflow/edit-journey';
import { hasNext, replaceState, withoutNext } from '$lib/schema/workflow/edit-state';
import type { WorkingChoice, WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';

/*
	Taking steps and lines out of the journey. Only what the person chose is taken out. Nothing is joined up or
	pointed somewhere else for them, because a journey is allowed to be in pieces while it is being built, and the
	pieces left over are reported when the journey is checked before it is passed on.

	1. A step that loses the step it continued to is left with nothing after it.
	2. A decision that loses the state one of its ways out led to keeps that way out, with its rule, leading
	   nowhere. The decision stays however many of its ways out lead somewhere.
	3. A route a state can do without, an answer that is not valid, a timeout or a named error, is simply taken
	   out.
	4. Whatever the removed state or line led to is left where it is, with nothing leading to it.
	5. Taking out the state the journey starts at leaves the journey with no start, so the start dot has no line
	   until the person draws one.
*/

// Everything one press of Delete removed from the process: states, and lines between states.
export type DeletedFromJourney = {
	stateCodes: string[];
	lines: Array<{ source: string; path: (string | number)[]; target: string }>;
};

/**
 * Tells whether a route is one a state can do without, so it can be taken out and not only pointed somewhere else.
 */
function isOptionalRoute(state: WorkingState, path: (string | number)[]): boolean {
	switch (path[0]) {
		case 'on_invalid':
			return state.state_type === 'input' && state.on_invalid !== undefined;
		case 'timeout':
			return state.state_type === 'input' && state.timeout !== undefined;
		case 'catch':
			return (state.state_type === 'api_call' || state.state_type === 'invoke') && state.catch?.[Number(path[1])] !== undefined;
		default:
			return false;
	}
}

/**
 * Returns a copy of the state without an optional route. A timeout is a time and a route together, so taking
 * its route out takes the whole timeout out. A list that ends up empty is removed, so the saved state is the
 * same as if it never had one.
 */
function withoutOptionalRoute(state: WorkingState, path: (string | number)[]): WorkingState {
	const copy: Record<string, unknown> = { ...state };

	if (path[0] === 'on_invalid') delete copy.on_invalid;
	if (path[0] === 'timeout') delete copy.timeout;

	if (path[0] === 'catch' && (state.state_type === 'api_call' || state.state_type === 'invoke')) {
		const clauses = (state.catch ?? []).filter((_, index) => index !== Number(path[1]));
		if (clauses.length > 0) copy.catch = clauses;
		else delete copy.catch;
	}

	return copy as WorkingState;
}

/**
 * Returns a copy of a decision in which one way out leads nowhere. The way out is named by where it sits, a rule
 * or the default. A rule keeps its test and its place, so the decision still knows which answer the way out is for.
 */
function withoutWayOut(choice: WorkingChoice, path: (string | number)[]): WorkingState {
	if (path[0] === 'default') {
		const { default: _taken, ...rest } = choice;
		return rest;
	}

	return {
		...choice,
		rules: choice.rules.map((rule, index) => {
			if (index !== Number(path[1])) return rule;
			const { next: _taken, ...test } = rule;
			return test;
		})
	};
}

/**
 * Takes lines and states out of the process, and says why when nothing could
 * be taken out. The process that is given in is never changed.
 */
export function deleteFromJourney(process: WorkingProcess, deleted: DeletedFromJourney): EditResult {
	let current = process;
	let changed = false;

	// Takes one line out. Returns whether anything was done, so a line that cannot be taken out is not counted.
	function dropLine(sourceCode: string, path: (string | number)[]): boolean {
		const source = current.states[sourceCode];
		if (!source) return false;

		if (path[0] === 'next' && hasNext(source)) {
			// A step with nothing after it has no line to take out.
			if (source.next === undefined) return false;
			current = replaceState(current, sourceCode, withoutNext(source));
			return true;
		}
		if (source.state_type === 'choice' && (path[0] === 'rules' || path[0] === 'default')) {
			// A way out that already leads nowhere has no line to take out.
			const target = path[0] === 'default' ? source.default : source.rules[Number(path[1])]?.next;
			if (target === undefined) return false;
			current = replaceState(current, sourceCode, withoutWayOut(source, path));
			return true;
		}
		if (isOptionalRoute(source, path)) {
			current = replaceState(current, sourceCode, withoutOptionalRoute(source, path));
			return true;
		}
		return false;
	}

	// Takes a state out, with every line that led to it.
	function dropState(code: string) {
		if (!(code in current.states)) return;

		// Every route that led here is taken out one at a time, until none is left or one cannot be taken out.
		for (let guard = 0; guard < 100; guard += 1) {
			const leadsHere = routesInto(current, code).find(({ source }) => source !== code);
			if (!leadsHere || !dropLine(leadsHere.source, leadsHere.route.path)) break;
		}

		const { [code]: _gone, ...states } = current.states;
		// The process is left with no start when the state it started at goes.
		const { start, ...rest } = current;
		current = start === code ? { ...rest, states } : { ...current, states };
		changed = true;
	}

	for (const line of deleted.lines) {
		if (dropLine(line.source, line.path)) changed = true;
	}
	for (const code of deleted.stateCodes) dropState(code);

	if (!changed) {
		return { ok: false, reason: 'There is nothing to take out there.' };
	}
	return { ok: true, process: current };
}
