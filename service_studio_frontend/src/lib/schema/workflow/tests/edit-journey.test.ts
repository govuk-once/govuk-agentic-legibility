import { describe, expect, it } from 'vitest';
import { addBranch, addLooseStep, addStepBeforeStart, drawLine, endJourneyAt, routeToTargets } from '../edit-journey';
import { reachableInOrder } from '../journey-order';
import { isUndecidedRule } from '../placeholders';
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

describe('addLooseStep', () => {
	it('adds a message step with nothing after it and no end', () => {
		const added = addLooseStep(line());
		expect(added.process.states[added.code]).toMatchObject({ state_type: 'output', channel: 'transcript' });
		expect(added.process.states[added.code]).not.toHaveProperty('next');
		expect(Object.keys(added.process.states).sort()).toEqual(['a', 'b', 'c', 'end', added.code].sort());
	});

	it('leaves the journey as it was, so nothing leads to the new step yet', () => {
		const added = addLooseStep(line());
		expect(reachableInOrder(added.process)).toEqual(['a', 'b', 'end']);
	});

	it('gives each new step its own name', () => {
		const first = addLooseStep(line());
		const second = addLooseStep(first.process);
		expect(second.code).not.toBe(first.code);
	});

	it('takes a line drawn from it to another step as its next', () => {
		const added = addLooseStep(line());
		const drawn = ok(drawLine(added.process, added.code, 'b'));
		expect(drawn.process.states[added.code]).toMatchObject({ next: 'b' });
	});

	it('is led to by a step that goes on, with a decision for the old route and the new one', () => {
		const added = addLooseStep(line());
		const drawn = ok(drawLine(added.process, 'a', added.code));
		const a = drawn.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should still be a wait that continues somewhere');
		expect(drawn.process.states[a.next]).toMatchObject({ state_type: 'choice', rules: [{ next: 'b' }], default: added.code });
	});
});

describe('addStepBeforeStart', () => {
	it('adds a step that becomes the start and continues to the old start', () => {
		const result = ok(addStepBeforeStart(line()));
		expect(result.process.start).toBe(result.code);
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
