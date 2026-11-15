import { describe, expect, it } from 'vitest';
import { removeUnreachableStates, routesInto } from '../edit-process';
import type { Process } from '../process';
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

	it('leaves the process with no start when the first step is removed, and moves it on to nothing', () => {
		const process = ok(deleteFromJourney(line(), { stateCodes: ['a'], lines: [] }));
		expect(process).not.toHaveProperty('start');
		expect(Object.keys(process.states)).toEqual(['b', 'c', 'end']);
	});

	it('keeps a decision that loses the state a rule led to, with the rule leading nowhere', () => {
		const process = build('d', { d: { state_type: 'choice', rules: [rule('a')], default: 'b' }, a: finish, b: finish });
		const result = ok(deleteFromJourney(process, { stateCodes: ['a'], lines: [] }));
		// The decision stays with one way out left, and the rule keeps its test.
		expect(result.states.d).toEqual({ state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'x' } }], default: 'b' });
		expect(result.start).toBe('d');
	});

	it('keeps every rule when the state the default led to goes, and leaves the default leading nowhere', () => {
		const process = build('d', {
			d: { state_type: 'choice', rules: [rule('a'), rule('b', 'y')], default: 'c' },
			a: finish,
			b: finish,
			c: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: ['c'], lines: [] }));
		expect(result.states.d).toEqual({ state_type: 'choice', rules: [rule('a'), rule('b', 'y')] });
	});

	it('takes out every way into a state that one decision leads to more than once', () => {
		const process = build('d', { d: { state_type: 'choice', rules: [rule('a'), rule('a', 'y')], default: 'a' }, a: finish });
		const result = ok(deleteFromJourney(process, { stateCodes: ['a'], lines: [] }));
		expect(routesOf(result.states.d)).toEqual([]);
		expect(result.states.d).toMatchObject({ rules: [{ when: { path: 'x' } }, { when: { path: 'y' } }] });
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

	it('takes out a decision and nothing else, so the step before it and its branches are left as loose pieces', () => {
		const process = build('a', {
			a: wait('d'),
			d: { state_type: 'choice', rules: [rule('x')], default: 'y' },
			x: wait('end'),
			y: wait('end'),
			end: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: ['d'], lines: [] }));
		expect(result.states.a).not.toHaveProperty('next');
		expect(Object.keys(result.states)).toEqual(['a', 'x', 'y', 'end']);
	});

	it('does not change the process it was given', () => {
		const process = line();
		const before = JSON.stringify(process);
		deleteFromJourney(process, { stateCodes: ['b'], lines: [] });
		expect(JSON.stringify(process)).toBe(before);
	});
});

describe('deleteFromJourney taking out a line', () => {
	it('leaves a step that loses its next with nothing after it, and leaves what the line led to', () => {
		const result = ok(deleteFromJourney(line(), { stateCodes: [], lines: [{ source: 'a', path: ['next'], target: 'b' }] }));
		expect(result.states.a).not.toHaveProperty('next');
		expect(Object.keys(result.states)).toEqual(['a', 'b', 'c', 'end']);
	});

	it('takes out a line into an end and leaves the end', () => {
		const result = ok(deleteFromJourney(line(), { stateCodes: [], lines: [{ source: 'c', path: ['next'], target: 'end' }] }));
		expect(result.states.c).not.toHaveProperty('next');
		expect(result.states.end).toBeDefined();
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

	it('takes one way out of a decision by leaving its rule leading nowhere, and leaves what it led to', () => {
		const process = build('d', {
			d: { state_type: 'choice', rules: [rule('a'), rule('b', 'y')], default: 'c' },
			a: finish,
			b: finish,
			c: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'd', path: ['rules', 0, 'next'], target: 'a' }] }));
		expect(routesOf(result.states.d)).toEqual([
			{ target: 'b', path: ['rules', 1, 'next'], kind: 'rule' },
			{ target: 'c', path: ['default'], kind: 'default' }
		]);
		expect(result.states.a).toBeDefined();
	});

	it('has no line to take out of a way out that already leads nowhere', () => {
		const process = build('d', { d: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'x' } }] }, a: finish });
		expect(deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'd', path: ['rules', 0, 'next'], target: 'a' }] }).ok).toBe(false);
		expect(deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'd', path: ['default'], target: 'a' }] }).ok).toBe(false);
	});

	it('takes out an error route and leaves the branch it led to', () => {
		const process = build('a', {
			a: call('end', { catch: [{ on: 'any', next: 'sorry' }] }),
			sorry: wait('failed'),
			failed: { state_type: 'end', status: 'failed' },
			end: finish
		});
		const result = ok(deleteFromJourney(process, { stateCodes: [], lines: [{ source: 'a', path: ['catch', 0, 'next'], target: 'sorry' }] }));
		expect(result.states.a).not.toHaveProperty('catch');
		expect(Object.keys(result.states)).toEqual(['a', 'sorry', 'failed', 'end']);
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
