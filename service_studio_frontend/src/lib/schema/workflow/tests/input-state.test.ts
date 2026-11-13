import { describe, expect, it } from 'vitest';
import { exampleStatesOfType } from './example-states';
import { answerDefinitionSchema, inputStateSchema, inputTimeoutSchema } from '../input-state';

describe('inputStateSchema with the real examples', () => {
	it('accepts every input state in the example files', () => {
		const states = exampleStatesOfType('input');
		expect(states.length).toBeGreaterThan(50);
		for (const state of states) {
			const result = inputStateSchema.safeParse(state);
			expect(result.success, JSON.stringify(state)).toBe(true);
		}
	});
});

describe('answerDefinitionSchema', () => {
	it('accepts a yes or no answer', () => {
		expect(answerDefinitionSchema.safeParse({ kind: 'boolean' }).success).toBe(true);
		expect(answerDefinitionSchema.safeParse({ kind: 'boolean', default: false }).success).toBe(true);
	});

	it('accepts a text answer with a pattern and a tidy up step', () => {
		const answer = {
			kind: 'string',
			pattern: '^[0-9]{9}$',
			normalise: 'upper_trim',
			max_length: 9,
			invalid_message: 'Enter nine digits.'
		};
		expect(answerDefinitionSchema.safeParse(answer).success).toBe(true);
	});

	it('rejects a pattern that is not a valid regular expression', () => {
		expect(answerDefinitionSchema.safeParse({ kind: 'string', pattern: '([a-z' }).success).toBe(false);
	});

	it('rejects an unknown normalise step and a max_length that is not a whole number', () => {
		expect(answerDefinitionSchema.safeParse({ kind: 'string', normalise: 'shout' }).success).toBe(false);
		expect(answerDefinitionSchema.safeParse({ kind: 'string', max_length: 2.5 }).success).toBe(false);
	});

	it('accepts a choice with written out options', () => {
		const options = [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }];
		expect(answerDefinitionSchema.safeParse({ kind: 'select_one', options }).success).toBe(true);
		expect(answerDefinitionSchema.safeParse({ kind: 'select_many', options, default: ['yes'] }).success).toBe(true);
	});

	it('accepts a choice whose options are read from a variable', () => {
		const answer = { kind: 'select_one', options_from: 'addresses.addresses', value_key: 'id', label_key: 'label' };
		expect(answerDefinitionSchema.safeParse(answer).success).toBe(true);
	});

	it('rejects a choice with no options, with an empty list, or with both forms', () => {
		const options = [{ value: 'a', label: 'A' }];
		expect(answerDefinitionSchema.safeParse({ kind: 'select_one' }).success).toBe(false);
		expect(answerDefinitionSchema.safeParse({ kind: 'select_one', options: [] }).success).toBe(false);
		expect(answerDefinitionSchema.safeParse({ kind: 'select_one', options, options_from: 'list' }).success).toBe(false);
	});

	it('rejects an option with no label', () => {
		expect(answerDefinitionSchema.safeParse({ kind: 'select_one', options: [{ value: 'a' }] }).success).toBe(false);
	});

	it('accepts a file upload with its limits', () => {
		const answer = { kind: 'file_ref', accept: ['image/png', 'application/pdf'], max_bytes: 5000000, allow_skip: false, declared_only: true };
		expect(answerDefinitionSchema.safeParse(answer).success).toBe(true);
	});

	it('rejects a key that does not belong to the kind', () => {
		expect(answerDefinitionSchema.safeParse({ kind: 'boolean', pattern: '^x$' }).success).toBe(false);
		expect(answerDefinitionSchema.safeParse({ kind: 'string', options: [] }).success).toBe(false);
		expect(answerDefinitionSchema.safeParse({ kind: 'file_ref', pattern: '^x$' }).success).toBe(false);
	});

	it('rejects the fields key, which is not modelled', () => {
		expect(answerDefinitionSchema.safeParse({ kind: 'string', fields: [] }).success).toBe(false);
	});

	it('rejects a kind the document does not list', () => {
		expect(answerDefinitionSchema.safeParse({ kind: 'date' }).success).toBe(false);
	});
});

describe('inputTimeoutSchema', () => {
	it('accepts a written duration or a reference, with the state to go to', () => {
		expect(inputTimeoutSchema.safeParse({ after: 'PT5S', next: 'no_response' }).success).toBe(true);
		expect(inputTimeoutSchema.safeParse({ after: { $: 'reminder_after' }, next: 'no_response' }).success).toBe(true);
	});

	it('rejects a timeout with no state to go to or a vague duration', () => {
		expect(inputTimeoutSchema.safeParse({ after: 'PT5S' }).success).toBe(false);
		expect(inputTimeoutSchema.safeParse({ after: 'soon', next: 'x' }).success).toBe(false);
	});
});

describe('inputStateSchema', () => {
	const question = {
		state_type: 'input',
		prompt: 'Is your address correct?',
		schema: { kind: 'boolean' },
		assign: 'address_confirmed',
		next: 'check_answer'
	};

	it('accepts a question with the optional routes and notes', () => {
		const state = {
			...question,
			name: 'Confirm address',
			metadata: { description: 'Checks the address.' },
			on_invalid: 'ask_again',
			timeout: { after: 'P1D', next: 'give_up' }
		};
		expect(inputStateSchema.safeParse(state).success).toBe(true);
	});

	it('accepts the notes the form files carry: text, a number, true or false, null and nested answer settings', () => {
		const state = {
			...question,
			name: 'Are you applying for yourself',
			metadata: {
				forms_step_id: 'abc123',
				position: 2,
				page_heading: null,
				answer_type: 'selection',
				hint_text: 'Choose one answer.',
				optional: false,
				repeatable: false,
				answer_settings: {
					only_one_option: 'true',
					selection_options: [{ name: 'Yes', value: 'Yes', is_other: false, requires_text: false }],
					input_type: null
				}
			}
		};
		expect(inputStateSchema.safeParse(state).success).toBe(true);
	});

	it.each(['prompt', 'schema', 'assign', 'next'])('rejects a question with no %s', (key) => {
		const { [key as keyof typeof question]: _removed, ...state } = question;
		expect(inputStateSchema.safeParse(state).success).toBe(false);
	});

	it('rejects an empty prompt and an invalid variable path', () => {
		expect(inputStateSchema.safeParse({ ...question, prompt: '' }).success).toBe(false);
		expect(inputStateSchema.safeParse({ ...question, assign: 'not a path' }).success).toBe(false);
	});

	it('rejects a key the document does not list', () => {
		expect(inputStateSchema.safeParse({ ...question, fields: [] }).success).toBe(false);
	});
});
