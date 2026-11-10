import { describe, expect, it } from 'vitest';
import { routesInto } from '../edit-process';
import { removeUnreachableStates } from '../edit-process';
import { processSchema, type Process } from '../process';
import { routesOf } from '../routes';
import { deleteFromJourney } from '../remove-state';

const finish = { state_type: 'end', status: 'success' };
const wait = (next: string) => ({ state_type: 'wait', duration: 'PT1S', next });
const call = (next: string, extra: object = {}) => ({ state_type: 'api_call', method: 'GET', service: 's', url: '/u', next, ...extra });
const rule = (next: string, path = 'x') => ({ when: { op: 'is_true', path }, next });

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

const line = () => build('a', { a: wait('b'), b: wait('c'), c: wait('end'), end: finish });

// Narrows a result to its success case so a test can read the process.
function ok(result: ReturnType<typeof deleteFromJourney>) {
	if (!result.ok) throw new Error(`expected success but got: ${result.reason}`);
	return result.process;
}

describe('removeUnreachableStates', () => {
	it('takes out a state nothing leads to and the chain that only it led to', () => {
		const process = build('a', { a: wait('end'), x: wait('y'), y: wait('end'), end: finish });
		const cleaned = removeUnreachableStates(process, ['x']);
		expect(Object.keys(cleaned.states).sort()).toEqual(['a', 'end']);
	});

	it('keeps a state that something still leads to, and the start', () => {
		const process = build('a', { a: wait('b'), b: wait('end'), end: finish });
		expect(removeUnreachableStates(process, ['b', 'a'])).toBe(process);
	});
});

describe('deleteFromJourney taking out a step', () => {
	it('leaves the step before it with nothing after it, and leaves what came after on its own', () => {
		const process = ok(deleteFromJourney(line(), { stateCodes: ['b'], lines: [] }));
		expect(process.states.a).not.toHaveProperty('next');
		expect(process.states.b).toBeUndefined();
		// Taking a step out does not take out what it led on to.
		expect(process.states.c).toBeDefined();
		expect(Object.keys(process.states).some((code) => process.states[code].state_type === 'end' && code !== 'end')).toBe(false);
	});

	it('moves the start on to what the removed first step led to', () => {
		const process = ok(deleteFromJourney(line(), { stateCodes: ['a'], lines: [] }));
		expect(process.start).toBe('b');
	});

	it('takes the way on out of a decision, and leaves the decision out when one way is left', () => {
		const process = build('d', { d: { state_type: 'choice', rules: [rule('a')], default: 'b' }, a: finish, b: finish });
		const result = ok(deleteFromJourney(process, { stateCodes: ['a'], lines: [] }));
		// The decision has one way on left, so it goes and the start leads straight to the other.
		expect(result.states.d).toBeUndefined();
		expect(result.start).toBe('b');
	});

	it('keeps a decision with two ways on left, and makes the last rule the default when the default goes', () => {
		const process = build('d', {
			d: { state_type: 'choice', rules: [rule('a'), rule('b', 'y')], default: 'c' },
			a: finish,
			b: finish,
			c: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: ['c'], lines: [] }));
		expect(result.states.d).toMatchObject({ state_type: 'choice', rules: [{ next: 'a' }], default: 'b' });
	});

	it('takes out a named error route and an invalid answer route that led to it', () => {
		const process = build('a', {
			a: call('end', { catch: [{ on: 'any', next: 'sorry' }] }),
			sorry: finish,
			end: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: ['sorry'], lines: [] }));
		expect(result.states.a).not.toHaveProperty('catch');
	});

	it('takes out a decision and leaves the step before it with nothing after it, with its branches checked', () => {
		const process = build('a', {
			a: wait('d'),
			d: { state_type: 'choice', rules: [rule('x')], default: 'y' },
			x: wait('end'),
			y: wait('end'),
			end: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: ['d'], lines: [] }));
		expect(result.states.a).not.toHaveProperty('next');
		// Nothing else led to the branches, so they go with the decision, as ending the journey did before.
		expect(result.states.x).toBeUndefined();
		expect(result.states.y).toBeUndefined();
	});

	it('does not change the process it was given', () => {
		const process = line();
		const before = JSON.stringify(process);
		deleteFromJourney(process, { stateCodes: ['b'], lines: [] });
		expect(JSON.stringify(process)).toBe(before);
	});
});

describe('deleteFromJourney taking out a line', () => {
	it('leaves a step that loses its next with nothing after it, and takes out what only that line led to', () => {
		const result = ok(deleteFromJourney(line(), { stateCodes: [], lines: [{ source: 'a', path: ['next'], target: 'b' }] }));
		expect(result.states.a).not.toHaveProperty('next');
		expect(result.states.b).toBeUndefined();
		expect(result.states.c).toBeUndefined();
	});

	it('takes out a line into an end, and the end with it when nothing else leads there', () => {
		const result = ok(deleteFromJourney(line(), { stateCodes: [], lines: [{ source: 'c', path: ['next'], target: 'end' }] }));
		expect(result.states.c).not.toHaveProperty('next');
		expect(result.states.end).toBeUndefined();
	});

	it('keeps an end that another step still leads to', () => {
		const process = build('a', { a: wait('c'), b: wait('end'), c: wait('end'), end: finish });
		const result = ok(deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'c', path: ['next'], target: 'end' }] }));
		expect(result.states.c).not.toHaveProperty('next');
		expect(result.states.end).toBeDefined();
	});

	it('leaves every step that led to a shared end with nothing after it when that end is deleted', () => {
		const process = build('a', { a: wait('b'), b: wait('end'), c: wait('end'), end: finish });
		const result = ok(deleteFromJourney(process, { stateCodes: ['end'], lines: [] }));
		expect(result.states.b).not.toHaveProperty('next');
		expect(result.states.c).not.toHaveProperty('next');
		expect(result.states.a).toMatchObject({ next: 'b' });
	});

	it('leaves the step before an end with nothing after it when the end itself is deleted', () => {
		const result = ok(deleteFromJourney(line(), { stateCodes: ['end'], lines: [] }));
		expect(result.states.end).toBeUndefined();
		expect(result.states.c).not.toHaveProperty('next');
		expect(result.states.b).toMatchObject({ next: 'c' });
	});

	it('takes one way on out of a decision, and the branch that only it led to', () => {
		const process = build('d', {
			d: { state_type: 'choice', rules: [rule('a'), rule('b', 'y')], default: 'c' },
			a: finish,
			b: finish,
			c: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'd', path: ['rules', 0, 'next'], target: 'a' }] }));
		expect(routesOf(result.states.d).map((route) => route.target)).toEqual(['b', 'c']);
		expect(result.states.a).toBeUndefined();
	});

	it('takes out an error route and the branch that only it led to', () => {
		const process = build('a', {
			a: call('end', { catch: [{ on: 'any', next: 'sorry' }] }),
			sorry: wait('failed'),
			failed: { state_type: 'end', status: 'failed' },
			end: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'a', path: ['catch', 0, 'next'], target: 'sorry' }] }));
		expect(Object.keys(result.states).sort()).toEqual(['a', 'end']);
		expect(routesInto(result, 'sorry')).toEqual([]);
	});

	it('takes out a timeout together with its time', () => {
		const process = build('a', {
			a: { state_type: 'input', prompt: 'Q', schema: { kind: 'boolean' }, assign: 'a', next: 'end', timeout: { after: 'PT5S', next: 'gave_up' } },
			gave_up: finish,
			end: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'a', path: ['timeout', 'next'], target: 'gave_up' }] }));
		expect(result.states.a).not.toHaveProperty('timeout');
	});
});

describe('deleteFromJourney for a step that has nothing after it', () => {
	it('has no line to take out, so nothing is changed', () => {
		const process = build('a', { a: { state_type: 'wait', duration: 'PT1S' }, end: finish });
		const result = deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'a', path: ['next'], target: 'end' }] });
		expect(result.ok).toBe(false);
	});
});
