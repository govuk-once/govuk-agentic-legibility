import { describe, expect, it } from 'vitest';
import { exampleStatesOfType } from './example-states';
import { invokeStateSchema } from '../invoke-state';

describe('invokeStateSchema with the real examples', () => {
	it('accepts every invoke state in the example files', () => {
		const states = exampleStatesOfType('invoke');
		expect(states.length).toBeGreaterThan(10);
		for (const state of states) {
			const result = invokeStateSchema.safeParse(state);
			expect(result.success, JSON.stringify(state)).toBe(true);
		}
	});
});

describe('invokeStateSchema', () => {
	const invoke = { state_type: 'invoke', process: 'driver_details', next: 'update_address' };

	it('accepts an invoke with only a process and a next state', () => {
		expect(invokeStateSchema.safeParse(invoke).success).toBe(true);
	});

	it('accepts an invoke with input, a stored result and catch routes', () => {
		const state = {
			...invoke,
			name: 'Get the driver details',
			metadata: { description: 'Runs the driver section.' },
			input: { driver_id: { $: 'driver_id' }, attempts: 0 },
			assign: 'driver_info',
			catch: [{ on: 'cancelled', next: 'end_cancelled' }]
		};
		expect(invokeStateSchema.safeParse(state).success).toBe(true);
	});

	it.each(['process', 'next'])('rejects an invoke with no %s', (key) => {
		const { [key as keyof typeof invoke]: _removed, ...state } = invoke;
		expect(invokeStateSchema.safeParse(state).success).toBe(false);
	});

	it('rejects an input name that is not a valid path or a value that is not an expression', () => {
		expect(invokeStateSchema.safeParse({ ...invoke, input: { 'not a path': 1 } }).success).toBe(false);
		expect(invokeStateSchema.safeParse({ ...invoke, input: { a: { op: 'multiply' } } }).success).toBe(false);
	});

	it('rejects a catch clause with no next state', () => {
		expect(invokeStateSchema.safeParse({ ...invoke, catch: [{ on: 'any' }] }).success).toBe(false);
	});
});
