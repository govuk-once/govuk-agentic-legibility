import { describe, expect, it } from 'vitest';
import { redirectRoutes, routesInto } from '../edit-process';
import type { Process } from '../process';

const finish = { state_type: 'end', status: 'success' };

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

// A process with a call that has an error route, and a decision, so every kind of route is in use.
const branching = build('ask', {
	ask: { state_type: 'input', prompt: 'Q', schema: { kind: 'boolean' }, assign: 'a', next: 'decide', on_invalid: 'sorry' },
	decide: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'a' }, next: 'sorry' }], default: 'done' },
	sorry: finish,
	done: finish
});

describe('routesInto', () => {
	it('lists every route that leads into a state, with the state it leaves from', () => {
		const into = routesInto(branching, 'sorry');
		expect(into.map(({ source, route }) => `${source}:${route.path.join('.')}`)).toEqual(['ask:on_invalid', 'decide:rules.0.next']);
	});

	it('gives an empty list for a state nothing leads to', () => {
		expect(routesInto(branching, 'ask')).toEqual([]);
	});
});

describe('redirectRoutes', () => {
	it('points every kind of route and the start at the new state', () => {
		const redirected = redirectRoutes(branching, 'sorry', 'done');
		expect(routesInto(redirected, 'sorry')).toEqual([]);
		expect(routesInto(redirected, 'done')).toHaveLength(3);
	});

	it('moves the start of the process when the start is redirected', () => {
		expect(redirectRoutes(branching, 'ask', 'decide').start).toBe('decide');
	});

	it('leaves the process it was given unchanged', () => {
		const before = JSON.stringify(branching);
		redirectRoutes(branching, 'sorry', 'done');
		expect(JSON.stringify(branching)).toBe(before);
	});

	it('reuses a state that had no route to change', () => {
		const redirected = redirectRoutes(branching, 'sorry', 'done');
		expect(redirected.states.done).toBe(branching.states.done);
	});
});
