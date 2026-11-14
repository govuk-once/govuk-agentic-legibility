import { describe, expect, it } from 'vitest';
import { addBranch, addLooseStep, applyStateEdit, addStepBeforeStart, drawLine, endJourneyAt, isNewStepKind, routeToTargets } from '../edit-journey';
import { reachableInOrder } from '../journey-order';
import { isUndecidedRule, placeholderMessage, placeholderQuestion } from '../placeholders';
import { processSchema, type Process } from '../process';
import { routesOf } from '../routes';

const finish = { state_type: 'end', status: 'success' };
const wait = (next: string) => ({ state_type: 'wait', duration: 'PT1S', next });
const rule = (next: string) => ({ when: { op: 'is_true', path: 'x' }, next });

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

const line = () => build('a', { a: wait('b'), b: wait('end'), c: wait('end'), end: finish });

// Narrows a result to its success case so a test can read the process.
function ok(result: ReturnType<typeof drawLine>) {
	if (!result.ok) throw new Error(`expected success but got: ${result.reason}`);
	return result;
}

describe('routeToTargets', () => {
	it('continues straight to a single target', () => {
		const routed = routeToTargets(line(), ['c']);
		expect(routed.entry).toBe('c');
		expect(routed.process).toEqual(line());
	});

	it('puts a decision before several targets, with the last as the default', () => {
		const routed = routeToTargets(line(), ['b', 'c', 'end']);
		expect(routed.process.states[routed.entry]).toMatchObject({ state_type: 'choice', default: 'end', rules: [{ next: 'b' }, { next: 'c' }] });
		const choice = routed.process.states[routed.entry];
		if (choice.state_type === 'choice') expect(choice.rules.every((r) => isUndecidedRule(r.when))).toBe(true);
	});
});

describe('drawLine', () => {
	it('puts a decision after a step that already goes on, holding the old route and the new one', () => {
		const result = ok(drawLine(line(), 'a', 'c'));
		const a = result.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should still be a wait that continues somewhere');
		expect(result.process.states[a.next]).toMatchObject({ state_type: 'choice', rules: [{ next: 'b' }], default: 'c' });
		expect(processSchema.safeParse(result.process).success).toBe(true);
	});

	it('gives a step that only ends the journey the new line in place of its end', () => {
		const process = build('a', { a: wait('stop'), stop: finish, b: wait('end'), end: finish });
		const result = ok(drawLine(process, 'a', 'b'));
		expect(result.process.states.a).toMatchObject({ next: 'b' });
		// The end it gave up is taken out because nothing else led to it.
		expect(result.process.states.stop).toBeUndefined();
	});

	it('keeps an end that something else still leads to', () => {
		const process = build('d', {
			d: { state_type: 'choice', rules: [rule('a')], default: 'b' },
			a: wait('stop'),
			b: wait('stop'),
			c: wait('end'),
			stop: finish,
			end: finish
		});
		const result = ok(drawLine(process, 'a', 'c'));
		expect(result.process.states.stop).toBeDefined();
	});

	it('gives a decision a new rule before its default', () => {
		const process = build('d', { d: { state_type: 'choice', rules: [rule('a')], default: 'b' }, a: finish, b: finish, c: finish });
		const result = ok(drawLine(process, 'd', 'c'));
		const choice = result.process.states.d;
		if (choice.state_type !== 'choice') throw new Error('expected a choice');
		expect(choice.rules.map((r) => r.next)).toEqual(['a', 'c']);
		expect(isUndecidedRule(choice.rules[1].when)).toBe(true);
		expect(choice.default).toBe('b');
	});

	it('refuses a repeat, a line to itself, a line from an end and a line to a missing step', () => {
		expect(drawLine(line(), 'a', 'b').ok).toBe(false);
		expect(drawLine(line(), 'a', 'a').ok).toBe(false);
		expect(drawLine(line(), 'end', 'a').ok).toBe(false);
		expect(drawLine(line(), 'a', 'missing').ok).toBe(false);
	});

	it('does not change the process it was given', () => {
		const process = line();
		const before = JSON.stringify(process);
		drawLine(process, 'a', 'c');
		expect(JSON.stringify(process)).toBe(before);
	});
});

describe('endJourneyAt', () => {
	it('points a step at a new end and takes out what only its old route led to', () => {
		const result = ok(endJourneyAt(line(), 'a'));
		const a = result.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should still be a wait that continues somewhere');
		expect(result.process.states[a.next]).toMatchObject({ state_type: 'end', status: 'success' });
		expect(result.process.states.b).toBeUndefined();
		expect(processSchema.safeParse(result.process).success).toBe(true);
	});

	it('gives a decision the end as a new rule', () => {
		const process = build('d', { d: { state_type: 'choice', rules: [rule('a')], default: 'a' }, a: finish });
		const result = ok(endJourneyAt(process, 'd'));
		expect(routesOf(result.process.states.d)).toHaveLength(3);
	});

	it('refuses a step that already ends the journey and an end', () => {
		const process = build('a', { a: wait('stop'), stop: finish });
		expect(endJourneyAt(process, 'a').ok).toBe(false);
		expect(endJourneyAt(process, 'stop').ok).toBe(false);
	});
});

describe('isNewStepKind', () => {
	it('is true for a question and a message, which are the steps a person can add', () => {
		expect(isNewStepKind('input')).toBe(true);
		expect(isNewStepKind('output')).toBe(true);
	});

	it('is false for every other kind of state and for other text', () => {
		for (const kind of ['choice', 'end', 'assign', 'wait', 'invoke', 'api_call', 'step', 'toString', '']) {
			expect(isNewStepKind(kind), kind).toBe(false);
		}
	});
});

describe('addLooseStep', () => {
	it('adds a message step with nothing after it and no end', () => {
		const added = addLooseStep(line(), 'output');
		expect(added.process.states[added.code]).toEqual({ state_type: 'output', channel: 'transcript', message: placeholderMessage });
		expect(Object.keys(added.process.states).sort()).toEqual(['a', 'b', 'c', 'end', added.code].sort());
	});

	it('adds a question step with a text answer, saved in a variable named after the step, and nothing after it', () => {
		const added = addLooseStep(line(), 'input');
		expect(added.process.states[added.code]).toEqual({
			state_type: 'input',
			prompt: placeholderQuestion,
			schema: { kind: 'string' },
			assign: `answer_${added.code}`
		});
	});

	it('saves the answers of two new questions in different variables', () => {
		const first = addLooseStep(line(), 'input');
		const second = addLooseStep(first.process, 'input');
		expect(second.process.states[second.code]).toMatchObject({ assign: `answer_${second.code}` });
		expect(second.code).not.toBe(first.code);
	});

	it.each(['input', 'output'] as const)('gives a new %s step that the schema accepts once it is joined to the journey', (kind) => {
		const added = addLooseStep(line(), kind);
		const joined = ok(drawLine(ok(drawLine(added.process, 'c', added.code)).process, added.code, 'end'));
		expect(processSchema.safeParse(joined.process).success).toBe(true);
	});

	it('leaves the journey as it was, so nothing leads to the new step yet', () => {
		const added = addLooseStep(line(), 'output');
		expect(reachableInOrder(added.process)).toEqual(['a', 'b', 'end']);
	});

	it('gives each new step its own name', () => {
		const first = addLooseStep(line(), 'output');
		const second = addLooseStep(first.process, 'output');
		expect(second.code).not.toBe(first.code);
	});

	it('takes a line drawn from it to another step as its next', () => {
		const added = addLooseStep(line(), 'output');
		const drawn = ok(drawLine(added.process, added.code, 'b'));
		expect(drawn.process.states[added.code]).toMatchObject({ next: 'b' });
	});

	it('is led to by a step that goes on, with a decision for the old route and the new one', () => {
		const added = addLooseStep(line(), 'output');
		const drawn = ok(drawLine(added.process, 'a', added.code));
		const a = drawn.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should still be a wait that continues somewhere');
		expect(drawn.process.states[a.next]).toMatchObject({ state_type: 'choice', rules: [{ next: 'b' }], default: added.code });
	});
});

describe('addStepBeforeStart', () => {
	it.each(['input', 'output'] as const)('adds a %s step that becomes the start and continues to the old start', (kind) => {
		const result = ok(addStepBeforeStart(line(), kind));
		expect(result.process.start).toBe(result.code);
		expect(result.process.states[result.code!]).toMatchObject({ state_type: kind, next: 'a' });
		expect(reachableInOrder(result.process)).toEqual([result.code, 'a', 'b', 'end']);
		expect(processSchema.safeParse(result.process).success).toBe(true);
	});
});

describe('addBranch', () => {
	it('gives a step a decision holding its old route and the new targets', () => {
		const result = ok(addBranch(line(), 'a', ['c', 'end']));
		const a = result.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should still be a wait that continues somewhere');
		expect(result.process.states[a.next]).toMatchObject({ state_type: 'choice', rules: [{ next: 'b' }, { next: 'c' }], default: 'end' });
		expect(result.code).toBe(a.next);
	});

	it('leaves out the end of a step that only ended the journey', () => {
		const process = build('a', { a: wait('stop'), stop: finish, b: wait('end'), c: wait('end'), end: finish });
		const result = ok(addBranch(process, 'a', ['b', 'c']));
		expect(result.process.states.stop).toBeUndefined();
		const a = result.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should still be a wait that continues somewhere');
		expect(result.process.states[a.next]).toMatchObject({ state_type: 'choice', rules: [{ next: 'b' }], default: 'c' });
	});

	it('does not repeat a way on a decision already has', () => {
		const process = build('d', { d: { state_type: 'choice', rules: [rule('a')], default: 'b' }, a: finish, b: finish, c: finish });
		const result = ok(addBranch(process, 'd', ['a', 'c']));
		const choice = result.process.states.d;
		if (choice.state_type !== 'choice') throw new Error('expected a choice');
		expect(choice.rules.map((r) => r.next)).toEqual(['a', 'c']);
	});
});

describe('a step with nothing after it', () => {
	const unfinished = () => build('a', { a: { state_type: 'wait', duration: 'PT1S' }, b: wait('end'), c: wait('end'), end: finish });

	it('takes a line drawn from it as its next', () => {
		const result = ok(drawLine(unfinished(), 'a', 'b'));
		expect(result.process.states.a).toMatchObject({ state_type: 'wait', next: 'b' });
	});

	it('is ended with a new end and nothing else is taken out', () => {
		const result = ok(endJourneyAt(unfinished(), 'a'));
		const a = result.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should now continue somewhere');
		expect(result.process.states[a.next]).toMatchObject({ state_type: 'end', status: 'success' });
		expect(Object.keys(result.process.states).sort()).toEqual(['a', 'b', 'c', 'end', a.next].sort());
	});

	it('is given a decision of only the new targets when it branches', () => {
		const result = ok(addBranch(unfinished(), 'a', ['b', 'c']));
		const a = result.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should now continue somewhere');
		expect(result.process.states[a.next]).toMatchObject({ state_type: 'choice', rules: [{ next: 'b' }], default: 'c' });
	});
});

describe('applyStateEdit', () => {
	const renamed = (next?: string) => ({ state_type: 'wait', duration: 'PT1S', name: 'Pause', ...(next ? { next } : {}) }) as never;

	it('puts the changed state into the process and leaves the rest as it was', () => {
		const result = applyStateEdit(line(), 'a', renamed('b'), false);
		expect(result.states.a).toMatchObject({ name: 'Pause', next: 'b' });
		expect(Object.keys(result.states).sort()).toEqual(['a', 'b', 'c', 'end']);
	});

	it('makes the end in the same change when the state is to end the journey, keeping the edit', () => {
		const result = applyStateEdit(line(), 'c', renamed('end'), true);
		// c already ended the journey, so it keeps the end it had.
		expect(result.states.c).toMatchObject({ name: 'Pause', next: 'end' });

		const ended = applyStateEdit(line(), 'b', renamed('end'), true);
		expect(ended.states.b).toMatchObject({ name: 'Pause', next: 'end' });

		const fromMiddle = applyStateEdit(build('a', { a: wait('b'), b: wait('end'), end: finish }), 'a', renamed('b'), true);
		const a = fromMiddle.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should continue to its new end');
		expect(a.name).toBe('Pause');
		expect(fromMiddle.states[a.next]).toMatchObject({ state_type: 'end' });
		expect(fromMiddle.states.b).toBeUndefined();
	});

	it('takes out an end that only this state led to when it now continues somewhere else', () => {
		const process = build('a', { a: wait('stop'), stop: finish, b: wait('end'), end: finish });
		const result = applyStateEdit(process, 'a', renamed('b'), false);
		expect(result.states.stop).toBeUndefined();
		expect(result.states.a).toMatchObject({ next: 'b' });
	});

	it('keeps a step it used to lead to, because only an end is cleared away', () => {
		const result = applyStateEdit(line(), 'a', renamed('c'), false);
		expect(result.states.b).toBeDefined();
	});
});
