import { removeUnreachableStates, redirectRoutes, routesInto } from './edit-process';
import type { EditResult } from './edit-journey';
import { hasNext, replaceState, withoutNext } from './edit-state';
import type { WorkingProcess, WorkingState } from './working-process';
import { routesOf } from './routes';

/*
	Taking steps and lines out of the journey when Delete is pressed.

	1. A step that loses the step it continued to is left with nothing after it. The person decides where it
	   goes next, or gives it an end, so nothing is added for them.
	2. A line into an end is taken out like any other line. The end goes too when nothing else leads to it,
	   so deleting an end dot leaves the step before it with nothing after it.
	3. A decision that loses a way on keeps the others. When only one is left the decision is not needed and
	   whatever led to it leads straight to that one. When the default is lost, the last rule becomes it.
	4. A route a state can do without, an answer that is not valid, a timeout or a named error, is simply taken
	   out.
	5. Taking a line out, or a decision, then checks what it led to. Anything nothing else leads to is taken
	   out as well, and so on down the branch. Taking a step out does not, so what it led on to is left, and the
	   panel tells the person that nothing leads to it.
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
 * Takes lines and states out of the process, and says why when nothing could
 * be taken out. The process that is given in is never changed.
 */
export function deleteFromJourney(process: WorkingProcess, deleted: DeletedFromJourney): EditResult {
	let current = process;
	let changed = false;
	// The states to check for being left on their own once everything is taken out.
	const roots: string[] = [];

	// Takes one way on out of a decision. The way is named by where it sits, a rule or the default.
	function dropChoiceBranch(choiceCode: string, path: (string | number)[]) {
		const choice = current.states[choiceCode];
		if (choice?.state_type !== 'choice') return;

		const branches = [...choice.rules.map((rule) => ({ target: rule.next, rule })), { target: choice.default, rule: undefined }];
		const index = path[0] === 'default' ? branches.length - 1 : Number(path[1]);
		const remaining = branches.filter((_, position) => position !== index);

		// With one way on left, the decision is not needed, so whatever led to it leads straight there.
		if (remaining.length === 1) {
			const joined = redirectRoutes(current, choiceCode, remaining[0].target);
			const { [choiceCode]: _gone, ...states } = joined.states;
			current = { ...joined, states };
			return;
		}

		// The last way on left is the default, so it loses its rule if it had one.
		const last = remaining[remaining.length - 1];
		const rules = remaining.slice(0, -1).flatMap((branch) => (branch.rule ? [branch.rule] : []));
		current = replaceState(current, choiceCode, { ...choice, rules, default: last.target });
	}

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
			dropChoiceBranch(sourceCode, path);
			return true;
		}
		if (isOptionalRoute(source, path)) {
			current = replaceState(current, sourceCode, withoutOptionalRoute(source, path));
			return true;
		}
		return false;
	}

	// Takes a state out and sorts out everything that led to it.
	function dropState(code: string) {
		const state = current.states[code];
		if (!state) return;

		// Where the journey carries on if this was the start. A decision carries on by its default.
		const wayOn = hasNext(state) ? state.next : state.state_type === 'choice' ? state.default : undefined;
		// Taking out a decision ends the step it came from, so the branches it led to are checked afterwards.
		if (state.state_type === 'choice') roots.push(...routesOf(state).map((route) => route.target));

		// Every route that led here is dealt with one at a time, because dealing with one can change the next.
		for (let guard = 0; guard < 100; guard += 1) {
			const leadsHere = routesInto(current, code).find(({ source }) => source !== code);
			if (!leadsHere || !dropLine(leadsHere.source, leadsHere.route.path)) break;
		}

		// The start moves on to what this state led to, or to the first state left when it led nowhere.
		const { [code]: _gone, ...states } = current.states;
		let start = current.start;
		if (start === code) start = wayOn && wayOn !== code && wayOn in states ? wayOn : (Object.keys(states)[0] ?? code);
		current = { ...current, start, states };
		changed = true;
	}

	for (const line of deleted.lines) {
		if (dropLine(line.source, line.path)) {
			changed = true;
			roots.push(line.target);
		}
	}
	for (const code of deleted.stateCodes) dropState(code);

	if (!changed) {
		return { ok: false, reason: 'There is nothing to take out there.' };
	}
	return { ok: true, process: removeUnreachableStates(current, roots) };
}
