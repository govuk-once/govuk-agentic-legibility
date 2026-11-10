import { describe, expect, it } from 'vitest';
import { reachableInOrder } from '../journey-order';
import { canMoveEarlier, canMoveLater, moveEarlier, moveLater } from '../move-state';
import { processSchema, type Process } from '../process';

const finish = { state_type: 'end', status: 'success' };
const wait = (next: string, extra: object = {}) => ({ state_type: 'wait', duration: 'PT1S', next, ...extra });

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

// A straight line of three steps and an end.
const line = () => build('a', { a: wait('b'), b: wait('c'), c: wait('end'), end: finish });

describe('moveLater', () => {
	it('swaps a step with the step after it, so the journey follows the new order', () => {
		const moved = moveLater(line(), 'b');
		expect(reachableInOrder(moved)).toEqual(['a', 'c', 'b', 'end']);
		expect(processSchema.safeParse(moved).success).toBe(true);
	});

	it('moves the start of the process when the first step moves down', () => {
		const moved = moveLater(line(), 'a');
		expect(moved.start).toBe('b');
		expect(reachableInOrder(moved)).toEqual(['b', 'a', 'c', 'end']);
	});

	it('keeps the error routes of both steps where they were', () => {
		const process = build('a', {
			a: wait('b'),
			b: { state_type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'end', catch: [{ on: 'any', next: 'a' }] },
			end: finish
		});
		const moved = moveLater(process, 'a');
		expect(moved.states.b).toMatchObject({ next: 'a', catch: [{ on: 'any', next: 'a' }] });
		expect(moved.states.a).toMatchObject({ next: 'end' });
	});

	it('points every route that led to the step at the step that took its place', () => {
		const process = build('ask', {
			ask: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'x' }, next: 'b' }], default: 'b' },
			b: wait('c'),
			c: wait('end'),
			end: finish
		});
		const moved = moveLater(process, 'b');
		expect(moved.states.ask).toMatchObject({ rules: [{ next: 'c' }], default: 'c' });
		expect(moved.states.c).toMatchObject({ next: 'b' });
	});

	it('does not move a step into a decision or an end', () => {
		const process = build('a', {
			a: wait('decide'),
			decide: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'x' }, next: 'end' }], default: 'end' },
			end: finish
		});
		expect(canMoveLater(process, 'a')).toBe(false);
		expect(canMoveLater(line(), 'c')).toBe(false);
		expect(moveLater(process, 'a')).toBe(process);
	});

	it('does not move a step past a point where two paths join', () => {
		const process = build('split', {
			split: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'x' }, next: 'a' }], default: 'b' },
			a: wait('b'),
			b: wait('c'),
			c: wait('end'),
			end: finish
		});
		// b is reached from both a and the decision, so a cannot swap with it.
		expect(canMoveLater(process, 'a')).toBe(false);
		expect(canMoveEarlier(process, 'b')).toBe(false);
		expect(canMoveLater(process, 'b')).toBe(true);
	});

	it('does not move a step past the start of the process', () => {
		const process = build('b', { a: wait('b'), b: wait('end'), end: finish });
		expect(canMoveLater(process, 'a')).toBe(false);
	});

	it('does not swap two steps that continue to each other', () => {
		const process = build('a', { a: wait('b'), b: wait('a') });
		expect(canMoveLater(process, 'a')).toBe(false);
	});

	it('does not move a step that is not in the process', () => {
		const process = line();
		expect(moveLater(process, 'missing')).toBe(process);
	});
});

describe('moveEarlier', () => {
	it('swaps a step with the step before it', () => {
		const moved = moveEarlier(line(), 'c');
		expect(reachableInOrder(moved)).toEqual(['a', 'c', 'b', 'end']);
	});

	it('cannot move the first step up', () => {
		expect(canMoveEarlier(line(), 'a')).toBe(false);
		expect(canMoveEarlier(line(), 'b')).toBe(true);
	});

	it('cannot move a step up when a decision leads to it', () => {
		const process = build('split', {
			split: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'x' }, next: 'a' }], default: 'a' },
			a: wait('end'),
			end: finish
		});
		expect(canMoveEarlier(process, 'a')).toBe(false);
		expect(moveEarlier(process, 'a')).toBe(process);
	});

	it('undoes a move down', () => {
		const original = line();
		const there = moveLater(original, 'b');
		const back = moveEarlier(there, 'b');
		expect(reachableInOrder(back)).toEqual(reachableInOrder(original));
	});
});

describe('moving steps that have nothing after them', () => {
	it('does not move a step down when it has no next', () => {
		const process = build('a', { a: { state_type: 'wait', duration: 'PT1S' }, end: finish });
		expect(canMoveLater(process, 'a')).toBe(false);
		expect(moveLater(process, 'a')).toBe(process);
	});

	it('does not swap with a step that has no next', () => {
		const process = build('a', { a: wait('b'), b: { state_type: 'wait', duration: 'PT1S' } });
		expect(canMoveLater(process, 'a')).toBe(false);
		expect(canMoveEarlier(process, 'b')).toBe(false);
	});
});
