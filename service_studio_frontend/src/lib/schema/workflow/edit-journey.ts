import { addState, removeUnreachableStates, setStart } from './edit-process';
import { hasNext, replaceState } from './edit-state';
import { defaultEndStatus, placeholderMessage, undecidedRule } from './placeholders';
import type { WorkingProcess, WorkingState } from './working-process';
import { routesOf } from './routes';

/*
	The changes a person makes to the journey on the canvas: drawing a line, ending the journey at a step,
	adding a step and adding a branch. They are written for the unified schema, where a step continues to one
	next state.

	1. A step has one next state, so a second line from a step does not add a second route. It puts a
	   decision after the step, with the old route and the new one as its two ways on. The decision starts
	   with the placeholder rule, which is worked out later. A step with nothing after it takes its first
	   line as its next.
	2. A step that only continues to an end counts as a step that ends the journey. A new line from it
	   replaces that end, because the end only showed where the step finished and the step now continues elsewhere.
	3. A decision gets a new way on as a new rule placed before its default, which stays the way it took when
	   no rule matches.
	4. Nothing here checks the result. The whole journey is checked once, before it is passed on.
*/

export type EditResult = { ok: true; process: WorkingProcess; code?: string } | { ok: false; reason: string };

// The names a new state is given before they are made unique within the process.
const newStepCode = 'new_step';
const newEndCode = 'new_end';
const newDecisionCode = 'new_decision';

/**
 * Returns the part of the process that leads on from a set of states, as a single state to continue to. One
 * target is continued to directly. Two or more become a decision, with a placeholder rule for every target
 * but the last, which is the way taken when no rule matches. The result carries the name of the state to
 * continue to.
 */
export function routeToTargets(process: WorkingProcess, targets: string[]): { process: WorkingProcess; entry: string } {
	if (targets.length === 1) return { process, entry: targets[0] };

	const decision: WorkingState = {
		type: 'choice',
		rules: targets.slice(0, -1).map((next) => ({ when: { ...undecidedRule }, next })),
		default: targets[targets.length - 1]
	};
	const added = addState(process, newDecisionCode, decision);
	return { process: added.process, entry: added.code };
}

/**
 * Draws a line from one state to another. A decision takes it as a new rule before its default. A step that
 * only ends the journey is given the new state in place of its end, and any other step is given a decision
 * with its old route and the new one. The result says why when the line cannot be drawn, in words a person
 * can read, so a graph can use the same answer to refuse a line while it is being dragged.
 */
export function drawLine(process: WorkingProcess, sourceCode: string, targetCode: string): EditResult {
	const source = process.states[sourceCode];

	// Both ends must be states of this process.
	if (!source || !(targetCode in process.states)) return { ok: false, reason: 'A line must join two steps.' };
	if (sourceCode === targetCode) return { ok: false, reason: 'A step cannot continue to itself.' };
	if (source.type === 'end') return { ok: false, reason: 'An end has nowhere to go.' };

	// A route that already leads there would only be repeated.
	if (routesOf(source).some((route) => route.target === targetCode && ['next', 'rule', 'default'].includes(route.kind))) {
		return { ok: false, reason: 'There is already a line between those two.' };
	}

	// A decision takes the new way on as a rule placed before its default.
	if (source.type === 'choice') {
		const rules = [...source.rules, { when: { ...undecidedRule }, next: targetCode }];
		return { ok: true, process: replaceState(process, sourceCode, { ...source, rules }) };
	}
	if (!hasNext(source)) return { ok: false, reason: 'That step cannot start a line.' };

	// A step with nothing after it yet takes the new line as its next.
	if (source.next === undefined) {
		return { ok: true, process: replaceState(process, sourceCode, { ...source, next: targetCode }) };
	}

	// A step that only ends the journey gives up its end for the new line, and the end goes if nothing else leads to it.
	if (process.states[source.next]?.type === 'end') {
		const replaced = replaceState(process, sourceCode, { ...source, next: targetCode });
		return { ok: true, process: removeUnreachableStates(replaced, [source.next]) };
	}

	// Any other step now has two ways on, which is a decision after it.
	const routed = routeToTargets(process, [source.next, targetCode]);
	return { ok: true, process: replaceState(routed.process, sourceCode, { ...source, next: routed.entry }) };
}

/**
 * Ends the journey at a step by pointing it at a new end state in place of wherever it went before. Whatever
 * only the old route led to is taken out. A decision cannot be ended as a whole, so it is given the end as a
 * new way on instead.
 */
export function endJourneyAt(process: WorkingProcess, sourceCode: string): EditResult {
	const source = process.states[sourceCode];
	if (!source) return { ok: false, reason: 'There is no step to end the journey at.' };
	if (source.type === 'end') return { ok: false, reason: 'That is already an end.' };

	const end: WorkingState = { type: 'end', status: defaultEndStatus };
	const added = addState(process, newEndCode, end);

	if (source.type === 'choice') {
		const drawn = drawLine(added.process, sourceCode, added.code);
		return drawn.ok ? { ...drawn, code: added.code } : drawn;
	}
	if (!hasNext(source)) return { ok: false, reason: 'That step cannot end the journey.' };
	const oldNext = source.next;
	if (oldNext !== undefined && process.states[oldNext]?.type === 'end') {
		return { ok: false, reason: 'The journey already ends there.' };
	}

	// A step with nothing after it has no old route to clear, so there is nothing to check for being left alone.
	const ended = replaceState(added.process, sourceCode, { ...source, next: added.code });
	return { ok: true, process: removeUnreachableStates(ended, oldNext === undefined ? [] : [oldNext]), code: added.code };
}

/**
 * Adds a new step that is not joined to the journey yet. It has nothing after it, because the person decides
 * where it goes by drawing a line, and a step may be left that way while a journey is being built. The step is a
 * message to the person with a placeholder wording. The result carries the name of the new step.
 */
export function addLooseStep(process: WorkingProcess): { process: WorkingProcess; code: string } {
	const step: WorkingState = { type: 'output', channel: 'transcript', message: placeholderMessage };
	return addState(process, newStepCode, step);
}

/**
 * Adds a new step in front of the start of the process. It continues to the old start and becomes the new
 * start, which is what dragging a line out of the start dot onto empty canvas does. The result carries the name
 * of the new step.
 */
export function addStepBeforeStart(process: WorkingProcess): EditResult {
	const step: WorkingState = { type: 'output', channel: 'transcript', message: placeholderMessage, next: process.start };
	const added = addState(process, newStepCode, step);
	return { ok: true, process: setStart(added.process, added.code), code: added.code };
}

/**
 * Gives a step several new ways on at once. A step is given a decision whose ways on are the route it
 * already had and the new targets, and a decision is given a new rule for each target it does not already
 * lead to. A step that only ended the journey gives up its end. The result carries the name of the decision
 * that has the new ways on.
 */
export function addBranch(process: WorkingProcess, sourceCode: string, targets: string[]): EditResult {
	const source = process.states[sourceCode];
	if (!source || source.type === 'end') return { ok: false, reason: 'That step cannot branch.' };

	if (source.type === 'choice') {
		const existing = new Set(routesOf(source).map((route) => route.target));
		const added = targets.filter((target) => !existing.has(target));
		const rules = [...source.rules, ...added.map((next) => ({ when: { ...undecidedRule }, next }))];
		return { ok: true, process: replaceState(process, sourceCode, { ...source, rules }), code: sourceCode };
	}
	if (!hasNext(source)) return { ok: false, reason: 'That step cannot branch.' };

	// The route the step already had stays as a way on, unless it only ended the journey or it had none.
	const oldNext = source.next;
	const replacesEnd = oldNext !== undefined && process.states[oldNext]?.type === 'end';
	const keeps = oldNext === undefined || replacesEnd ? [] : [oldNext];
	const ways = [...new Set([...keeps, ...targets])];

	const routed = routeToTargets(process, ways);
	const changed = replaceState(routed.process, sourceCode, { ...source, next: routed.entry });
	return { ok: true, process: removeUnreachableStates(changed, replacesEnd ? [oldNext] : []), code: routed.entry };
}
