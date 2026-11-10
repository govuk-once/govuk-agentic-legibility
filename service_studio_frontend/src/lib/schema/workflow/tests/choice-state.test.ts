import { describe, expect, it } from 'vitest';
import { choiceStateSchema } from '../choice-state';
import { exampleStatesOfType } from './example-states';

describe('choiceStateSchema with the real examples', () => {
	it('accepts every choice state in the example files', () => {
		const states = exampleStatesOfType('choice');
		expect(states.length).toBeGreaterThan(50);
		for (const state of states) {
			const result = choiceStateSchema.safeParse(state);
			expect(result.success, JSON.stringify(state)).toBe(true);
		}
	});
});

describe('choiceStateSchema', () => {
	const rule = { when: { op: 'is_true', path: 'attended' }, next: 'continue_claim' };

	it('accepts rules with a default', () => {
		const state = { type: 'choice', rules: [rule], default: 'missed_appointment' };
		expect(choiceStateSchema.safeParse(state).success).toBe(true);
	});

	it('accepts several rules, a title and notes', () => {
		const state = {
			type: 'choice',
			name: 'Did they attend?',
			metadata: { description: 'Splits on attendance.' },
			rules: [rule, { when: { op: 'gte', path: 'attempts', value: 3 }, next: 'give_up' }],
			default: 'ask_again'
		};
		expect(choiceStateSchema.safeParse(state).success).toBe(true);
	});

	it('rejects a choice with no default', () => {
		expect(choiceStateSchema.safeParse({ type: 'choice', rules: [rule] }).success).toBe(false);
	});

	it('rejects a choice with no rules', () => {
		expect(choiceStateSchema.safeParse({ type: 'choice', rules: [], default: 'x' }).success).toBe(false);
	});

	it('rejects a rule with an invalid condition or no next state', () => {
		const badCondition = { when: { op: 'eq', path: 'a' }, next: 'x' };
		expect(choiceStateSchema.safeParse({ type: 'choice', rules: [badCondition], default: 'x' }).success).toBe(false);
		expect(choiceStateSchema.safeParse({ type: 'choice', rules: [{ when: rule.when }], default: 'x' }).success).toBe(false);
	});

	it('rejects a next state, because a choice routes through its rules', () => {
		const state = { type: 'choice', rules: [rule], default: 'x', next: 'y' };
		expect(choiceStateSchema.safeParse(state).success).toBe(false);
	});
});
