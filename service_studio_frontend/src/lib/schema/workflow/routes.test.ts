import { describe, expect, it } from 'vitest';
import { exampleProcessFiles } from './example-states';
import { processSchema, type State } from './process';
import { routesOf } from './routes';

// Builds a state for a test. The cast is needed because each test supplies only the keys it uses.
const state = (value: unknown) => value as State;

describe('routesOf', () => {
	it('gives an end state no routes', () => {
		expect(routesOf(state({ type: 'end', status: 'success' }))).toEqual([]);
	});

	it.each(['output', 'assign', 'wait'])('gives a %s state its next route only', (type) => {
		expect(routesOf(state({ type, next: 'on' }))).toEqual([{ target: 'on', path: ['next'], kind: 'next' }]);
	});

	it('lists a choice rules in order, then the default', () => {
		const choice = state({
			type: 'choice',
			rules: [
				{ when: { op: 'is_true', path: 'a' }, next: 'first' },
				{ when: { op: 'is_true', path: 'b' }, next: 'second' }
			],
			default: 'fallback'
		});
		expect(routesOf(choice)).toEqual([
			{ target: 'first', path: ['rules', 0, 'next'], kind: 'rule' },
			{ target: 'second', path: ['rules', 1, 'next'], kind: 'rule' },
			{ target: 'fallback', path: ['default'], kind: 'default' }
		]);
	});

	it('includes the invalid answer and timeout routes of an input state', () => {
		const input = state({
			type: 'input',
			next: 'on',
			on_invalid: 'again',
			timeout: { after: 'PT5S', next: 'give_up' }
		});
		expect(routesOf(input)).toEqual([
			{ target: 'on', path: ['next'], kind: 'next' },
			{ target: 'again', path: ['on_invalid'], kind: 'on_invalid' },
			{ target: 'give_up', path: ['timeout', 'next'], kind: 'timeout' }
		]);
	});

	it.each(['call', 'invoke'])('includes the catch routes of a %s state', (type) => {
		const withCatch = state({
			type,
			next: 'on',
			catch: [
				{ on: 'api_failure', next: 'failed' },
				{ on: 'any', next: 'retry' }
			]
		});
		expect(routesOf(withCatch)).toEqual([
			{ target: 'on', path: ['next'], kind: 'next' },
			{ target: 'failed', path: ['catch', 0, 'next'], kind: 'catch' },
			{ target: 'retry', path: ['catch', 1, 'next'], kind: 'catch' }
		]);
	});

	it('finds a route for every state that is not an end in the real examples', () => {
		for (const file of exampleProcessFiles()) {
			const process = processSchema.parse(file);
			for (const [name, example] of Object.entries(process.states)) {
				const routes = routesOf(example);
				if (example.type === 'end') expect(routes, name).toEqual([]);
				else expect(routes.length, name).toBeGreaterThan(0);
			}
		}
	});
});
