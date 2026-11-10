import { describe, expect, it } from 'vitest';
import { exampleStatesOfType } from './example-states';
import {
	descriptionOf,
	endsTheJourney,
	hasNext,
	hasText,
	nothingYet,
	replaceState,
	textOf,
	withChoiceTargets,
	withNext,
	withNextChoice,
	withText,
	withTitleAndDescription
} from '../edit-state';
import { stateSchema, type Process, type State } from '../process';
import type { WorkingState } from '../working-process';

const state = (value: unknown) => value as State;
const wait = state({ state_type: 'wait', duration: 'PT1S', next: 'done' });

describe('withTitleAndDescription', () => {
	it('sets the title as the name and the description in the notes', () => {
		const updated = withTitleAndDescription(wait, 'Pause', 'Waits a second.');
		expect(updated).toEqual({ state_type: 'wait', duration: 'PT1S', next: 'done', name: 'Pause', metadata: { description: 'Waits a second.' } });
	});

	it('trims the text it is given', () => {
		const updated = withTitleAndDescription(wait, '  Pause  ', '  Waits.  ');
		expect(updated.name).toBe('Pause');
		expect(descriptionOf(updated)).toBe('Waits.');
	});

	it('removes the name and the description when they are blank, and the notes when nothing is left', () => {
		const titled = withTitleAndDescription(wait, 'Pause', 'Waits.');
		const cleared = withTitleAndDescription(titled, '   ', '');
		expect(cleared).toEqual(wait);
		expect(cleared).not.toHaveProperty('name');
		expect(cleared).not.toHaveProperty('metadata');
	});

	it('keeps other notes when the description changes or is removed', () => {
		const withNotes = state({ ...wait, metadata: { description: 'Old.', interaction: 'phone' } });
		expect(withTitleAndDescription(withNotes, '', 'New.').metadata).toEqual({ description: 'New.', interaction: 'phone' });
		expect(withTitleAndDescription(withNotes, '', '').metadata).toEqual({ interaction: 'phone' });
	});

	it('does not change the state it is given', () => {
		const before = JSON.stringify(wait);
		withTitleAndDescription(wait, 'Pause', 'Waits.');
		expect(JSON.stringify(wait)).toBe(before);
	});

	it.each(['input', 'output', 'api_call', 'choice', 'assign', 'invoke', 'wait', 'end'])(
		'gives a %s state from the real examples that the schema still accepts',
		(type) => {
			const states = exampleStatesOfType(type);
			expect(states.length).toBeGreaterThan(0);
			for (const real of states) {
				const updated = withTitleAndDescription(state(real), 'A new title', 'A new description.');
				expect(stateSchema.safeParse(updated).success).toBe(true);
			}
		}
	);
});

describe('descriptionOf', () => {
	it('gives an empty string when a state has no description', () => {
		expect(descriptionOf(wait)).toBe('');
		expect(descriptionOf(state({ ...wait, metadata: { interaction: 'phone' } }))).toBe('');
	});
});

describe('replaceState', () => {
	const process = { process_id: 'p', version: '0.1.0', vars: {}, start: 'a', states: { a: wait, done: state({ state_type: 'end', status: 'success' }) } } as unknown as Process;

	it('replaces one state and keeps the others as they were', () => {
		const changed = withTitleAndDescription(wait, 'Pause', '');
		const updated = replaceState(process, 'a', changed);

		expect(updated.states.a).toBe(changed);
		expect(updated.states.done).toBe(process.states.done);
		expect(process.states.a).toBe(wait);
	});
});

describe('withNext', () => {
	it('changes the state a step continues to and keeps everything else', () => {
		const titled = withTitleAndDescription(wait, 'Pause', 'Waits.');
		expect(withNext(titled, 'elsewhere')).toEqual({ ...titled, next: 'elsewhere' });
	});

	it('does not change the state it is given', () => {
		const before = JSON.stringify(wait);
		withNext(wait, 'elsewhere');
		expect(JSON.stringify(wait)).toBe(before);
	});

	it('returns a choice or an end as it is, because they have no single next state', () => {
		const choice = state({ state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'a' }, next: 'x' }], default: 'y' });
		const end = state({ state_type: 'end', status: 'success' });
		expect(withNext(choice, 'elsewhere')).toBe(choice);
		expect(withNext(end, 'elsewhere')).toBe(end);
	});

	it.each(['input', 'output', 'api_call', 'assign', 'invoke', 'wait'])(
		'gives a %s state from the real examples that the schema still accepts, ending up where it was sent',
		(type) => {
			const states = exampleStatesOfType(type);
			expect(states.length).toBeGreaterThan(0);
			for (const real of states) {
				const updated = withNext(state(real), 'somewhere_else');
				expect(stateSchema.safeParse(updated).success).toBe(true);
				expect(updated).toMatchObject({ next: 'somewhere_else' });
			}
		}
	);
});

describe('hasNext', () => {
	it.each([
		['input', true],
		['output', true],
		['api_call', true],
		['assign', true],
		['invoke', true],
		['wait', true],
		['choice', false],
		['end', false]
	])('says whether a %s state has a single next state: %s', (type, expected) => {
		expect(hasNext(state({ state_type: type }))).toBe(expected);
	});
});

describe('withChoiceTargets', () => {
	const choice = state({
		state_type: 'choice',
		rules: [
			{ when: { op: 'is_true', path: 'a' }, next: 'first' },
			{ when: { op: 'is_true', path: 'b' }, next: 'second' }
		],
		default: 'fallback'
	});

	it('changes where each rule and the default lead, and keeps the conditions', () => {
		const updated = withChoiceTargets(choice, ['one', 'two'], 'other');
		expect(updated).toEqual({
			state_type: 'choice',
			rules: [
				{ when: { op: 'is_true', path: 'a' }, next: 'one' },
				{ when: { op: 'is_true', path: 'b' }, next: 'two' }
			],
			default: 'other'
		});
	});

	it('changes one rule and leaves the other where it was', () => {
		const updated = withChoiceTargets(choice, ['first', 'two'], 'fallback');
		expect(updated).toMatchObject({ rules: [{ next: 'first' }, { next: 'two' }], default: 'fallback' });
	});

	it('keeps the target of a rule that was given none', () => {
		expect(withChoiceTargets(choice, ['one'], 'fallback')).toMatchObject({ rules: [{ next: 'one' }, { next: 'second' }] });
	});

	it('does not change the state it is given', () => {
		const before = JSON.stringify(choice);
		withChoiceTargets(choice, ['one', 'two'], 'other');
		expect(JSON.stringify(choice)).toBe(before);
	});

	it('returns a state that is not a choice as it is', () => {
		expect(withChoiceTargets(wait, ['one'], 'other')).toBe(wait);
	});

	it('gives a choice from the real examples that the schema still accepts', () => {
		const choices = exampleStatesOfType('choice');
		expect(choices.length).toBeGreaterThan(0);
		for (const real of choices) {
			const parsed = state(real) as Extract<State, { state_type: 'choice' }>;
			const updated = withChoiceTargets(parsed, parsed.rules.map(() => 'here'), 'there');
			expect(stateSchema.safeParse(updated).success).toBe(true);
			expect(updated).toMatchObject({ default: 'there' });
		}
	});
});

describe('hasText, textOf and withText', () => {
	const input = state({ state_type: 'input', prompt: 'Is it right?', schema: { kind: 'boolean' }, assign: 'ok', next: 'done' });
	const transcript = state({ state_type: 'output', channel: 'transcript', message: 'Thank you.', next: 'done' });
	const email = state({ state_type: 'output', channel: 'email', template: 'receipt', next: 'done' });

	it('offers the prompt of an input and the message of a transcript output, and nothing else', () => {
		expect(hasText(input)).toBe(true);
		expect(hasText(transcript)).toBe(true);
		expect(hasText(email)).toBe(false);
		expect(hasText(wait)).toBe(false);
		expect(textOf(input)).toBe('Is it right?');
		expect(textOf(transcript)).toBe('Thank you.');
		expect(textOf(email)).toBe('');
	});

	it('changes the prompt of an input and the message of a transcript output, trimmed', () => {
		expect(withText(input, '  Is it correct?  ')).toMatchObject({ prompt: 'Is it correct?', assign: 'ok', next: 'done' });
		expect(withText(transcript, 'All done.\n')).toMatchObject({ message: 'All done.', channel: 'transcript' });
	});

	it('returns an email output and any other state as it is', () => {
		expect(withText(email, 'New words')).toBe(email);
		expect(withText(wait, 'New words')).toBe(wait);
	});

	it('does not change the state it is given', () => {
		const before = JSON.stringify(input);
		withText(input, 'Changed');
		expect(JSON.stringify(input)).toBe(before);
	});

	it.each(['input', 'output'])('gives a %s state from the real examples that the schema still accepts', (type) => {
		const states = exampleStatesOfType(type);
		for (const real of states) {
			const updated = withText(state(real), 'Changed words');
			expect(stateSchema.safeParse(updated).success).toBe(true);
			if (hasText(updated)) expect(textOf(updated)).toBe('Changed words');
		}
	});
});

describe('withNextChoice', () => {
	const step = { state_type: 'wait', duration: 'PT1S', next: 'b' } as unknown as WorkingState;

	it('points the state at the chosen state', () => {
		expect(withNextChoice(step, 'c')).toMatchObject({ next: 'c' });
	});

	it('leaves the step with nothing after it when nothing yet is chosen', () => {
		expect(withNextChoice(step, nothingYet)).not.toHaveProperty('next');
	});

	it('leaves the state as it is when ending the journey is chosen, because the caller makes the end', () => {
		expect(withNextChoice(step, endsTheJourney)).toBe(step);
	});

	it('leaves a decision as it is, because it has no single next state', () => {
		const decision = { state_type: 'choice', rules: [], default: 'a' } as unknown as WorkingState;
		expect(withNextChoice(decision, nothingYet)).toBe(decision);
	});
});
