import { describe, expect, it } from 'vitest';
import { exampleProcessFiles } from './example-states';
import { journeyOrder, reachableInOrder } from './journey-order';
import { processSchema, type Process } from './process';

const finish = { type: 'end', status: 'success' };
const isTrue = { op: 'is_true', path: 'a' };

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

describe('reachableInOrder', () => {
	it('follows a straight line of states in order', () => {
		const process = build('a', {
			c: finish,
			b: { type: 'wait', duration: 'PT1S', next: 'c' },
			a: { type: 'wait', duration: 'PT1S', next: 'b' }
		});
		// The states are listed in a different order in the file, but the journey follows the routes.
		expect(reachableInOrder(process)).toEqual(['a', 'b', 'c']);
	});

	it('numbers a state after every branch that leads to it', () => {
		const process = build('ask', {
			ask: { type: 'wait', duration: 'PT1S', next: 'branch' },
			branch: { type: 'choice', rules: [{ when: isTrue, next: 'left' }], default: 'right' },
			left: { type: 'wait', duration: 'PT1S', next: 'join' },
			right: { type: 'wait', duration: 'PT1S', next: 'join' },
			join: finish
		});
		expect(reachableInOrder(process)).toEqual(['ask', 'branch', 'left', 'right', 'join']);
	});

	it('follows a choice rules in the order written, then the default', () => {
		const process = build('branch', {
			branch: {
				type: 'choice',
				rules: [
					{ when: isTrue, next: 'second_written_first' },
					{ when: isTrue, next: 'first_alphabetically' }
				],
				default: 'fallback'
			},
			first_alphabetically: finish,
			second_written_first: finish,
			fallback: finish
		});
		expect(reachableInOrder(process)).toEqual(['branch', 'second_written_first', 'first_alphabetically', 'fallback']);
	});

	it('visits a state once when the journey loops back', () => {
		const process = build('a', {
			a: { type: 'wait', duration: 'PT1S', next: 'b' },
			b: { type: 'choice', rules: [{ when: isTrue, next: 'a' }], default: 'c' },
			c: finish
		});
		expect(reachableInOrder(process)).toEqual(['a', 'b', 'c']);
	});

	it('leaves out a state that nothing leads to', () => {
		const process = build('a', { a: finish, orphan: finish });
		expect(reachableInOrder(process)).toEqual(['a']);
	});

	it('skips a route to a state that does not exist and a start that does not exist', () => {
		const half = build('a', { a: { type: 'wait', duration: 'PT1S', next: 'missing' } });
		expect(reachableInOrder(half)).toEqual(['a']);
		expect(reachableInOrder(build('nowhere', { a: finish }))).toEqual([]);
	});
});

describe('journeyOrder', () => {
	it('puts the states nothing leads to last, in the order the file lists them', () => {
		const process = build('a', { z_orphan: finish, a: finish, b_orphan: finish });
		expect(journeyOrder(process)).toEqual(['a', 'z_orphan', 'b_orphan']);
	});

	it('lists every state of every real process exactly once, starting at the start state', () => {
		for (const file of exampleProcessFiles()) {
			const process = processSchema.parse(file);
			const order = journeyOrder(process);

			expect(order[0]).toBe(process.start);
			expect([...order].sort()).toEqual(Object.keys(process.states).sort());
		}
	});
});
