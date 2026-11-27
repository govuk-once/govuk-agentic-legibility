import { describe, expect, it } from 'vitest';
import { stepWithItsAssign } from '$lib/schema/workflow/edit-process';
import { reachableInOrder } from '$lib/schema/workflow/journey-order';
import { canMoveEarlier, canMoveLater, moveEarlier, moveLater } from '$lib/schema/workflow/move-state';
import { processSchema, type Process } from '$lib/schema/workflow/process';

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

	it('moves a step past a point where two paths join, and the other path still leads to the step it led to', () => {
		const process = build('split', {
			split: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'x' }, next: 'a' }], default: 'b' },
			a: wait('b'),
			b: wait('c'),
			c: wait('end'),
			end: finish
		});
		expect(canMoveLater(process, 'a')).toBe(true);
		expect(canMoveEarlier(process, 'b')).toBe(true);

		// b is reached from both a and the decision. After the swap the decision leads to b on both of its ways out.
		const moved = moveLater(process, 'a');
		expect(moved.states.split).toMatchObject({ rules: [{ next: 'b' }], default: 'b' });
		expect(moved.states.b).toMatchObject({ next: 'a' });
		expect(moved.states.a).toMatchObject({ next: 'c' });
		expect(moveEarlier(process, 'b')).toEqual(moved);
	});

	it('moves a step past the step the process starts at, which stays the start', () => {
		const process = build('b', { a: wait('b'), b: wait('end'), end: finish });
		const moved = moveLater(process, 'a');
		expect(moved.start).toBe('b');
		expect(moved.states.b).toMatchObject({ next: 'a' });
		expect(moved.states.a).toMatchObject({ next: 'end' });
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

	it('swaps with a step that has no next, which leaves the step that moved down with nothing after it', () => {
		const process = build('a', { a: wait('b'), b: { state_type: 'wait', duration: 'PT1S' } });
		const moved = moveLater(process, 'a');
		expect(moved.start).toBe('b');
		expect(moved.states.b).toMatchObject({ next: 'a' });
		expect(moved.states.a).not.toHaveProperty('next');
		expect(moveEarlier(process, 'b')).toEqual(moved);
	});
});

describe('moving up when more than one step leads to a step', () => {
	it('has no single step to swap with, so the step cannot move up', () => {
		const process = build('a', { a: wait('c'), b: wait('c'), c: wait('end'), end: finish });
		expect(canMoveEarlier(process, 'c')).toBe(false);
		expect(moveEarlier(process, 'c')).toBe(process);
	});
});

describe('moving with a state that travels in front of a step', () => {
	const assign = (next: string) => ({ state_type: 'assign', set: { total: { literal: 1 } }, next });
	// A journey where the answer to b is saved by an assign placed in front of c, as a form does.
	const journey = () => build('a', { a: wait('b'), b: wait('save'), save: assign('c'), c: wait('d'), d: wait('end'), end: finish });

	it('finds nothing in front of a step unless the editor names it', () => {
		// Without the function the assign is a step like any other, so b swaps with it alone.
		expect(reachableInOrder(moveLater(journey(), 'b'))).toEqual(['a', 'save', 'b', 'c', 'd', 'end']);
	});

	it('moves a step down past the assign and the step it travels in front of together', () => {
		const moved = moveLater(journey(), 'b', stepWithItsAssign);
		expect(reachableInOrder(moved)).toEqual(['a', 'save', 'c', 'b', 'd', 'end']);
		expect(processSchema.safeParse(moved).success).toBe(true);
	});

	it('moves a step up with the assign in front of it, which gives the same journey', () => {
		expect(canMoveEarlier(journey(), 'c', stepWithItsAssign)).toBe(true);
		expect(moveEarlier(journey(), 'c', stepWithItsAssign)).toEqual(moveLater(journey(), 'b', stepWithItsAssign));
	});

	it('moves a step down with the assign in front of it, past the step after', () => {
		const moved = moveLater(journey(), 'c', stepWithItsAssign);
		expect(reachableInOrder(moved)).toEqual(['a', 'b', 'd', 'save', 'c', 'end']);
		expect(moveEarlier(journey(), 'd', stepWithItsAssign)).toEqual(moved);
	});

	it('undoes a move of the two together', () => {
		const there = moveLater(journey(), 'b', stepWithItsAssign);
		expect(reachableInOrder(moveEarlier(there, 'b', stepWithItsAssign))).toEqual(reachableInOrder(journey()));
	});
});
