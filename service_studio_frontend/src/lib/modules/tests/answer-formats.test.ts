import { describe, expect, it } from 'vitest';
import { answerTypeKey, answerTypesByKind } from '$lib/schema/workflow/answer-types';
import { answerDefinitionSchema } from '$lib/schema/workflow/input-state';
import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
import { addModule } from '$lib/modules/add-module';
import { answerFormatOf, answerFormats, formatsFor, withAnswerFormat, type AnswerFormatKey } from '$lib/modules/answer-formats';

const journey: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'hello', vars: {}, states: { hello: { state_type: 'output', channel: 'transcript', message: 'Hello' } } };
const typed: WorkingState = { state_type: 'input', prompt: 'Your email?', schema: { kind: 'string' }, assign: 'email' };

// Answers each format must accept and refuse, so a pattern copied or written wrongly is noticed.
const examples: Record<AnswerFormatKey, { accepts: string; refuses: string }> = {
	email: { accepts: 'name@example.com', refuses: 'name.example.com' },
	phone_number: { accepts: '07700900123', refuses: '12345' },
	postcode: { accepts: 'SW1A 1AA', refuses: 'SW1A' },
	date: { accepts: '31/12/2024', refuses: '2024-12-31' },
	national_insurance_number: { accepts: 'AB123456C', refuses: 'AB123456' },
	utr: { accepts: '1234567890', refuses: '123456789' },
	passport: { accepts: '123456789', refuses: '12345678A' },
	driving_licence: { accepts: 'MORGA753116SM9IJ', refuses: 'MORGA753116' },
	vat_number: { accepts: 'GB123456789', refuses: 'GB12345' },
	company_number: { accepts: 'SC123456', refuses: '1234567' },
	vehicle_registration: { accepts: 'AB12 CDE', refuses: 'A1' }
};

describe('answerFormats', () => {
	it.each(Object.keys(examples) as AnswerFormatKey[])('%s accepts a good answer and refuses a bad one', (key) => {
		const pattern = new RegExp(answerFormats[key].pattern);
		expect(pattern.test(examples[key].accepts)).toBe(true);
		expect(pattern.test(examples[key].refuses)).toBe(false);
	});

	it('names every format by an answer type for a typed answer', () => {
		for (const key of Object.keys(answerFormats)) expect(answerTypesByKind.string).toContain(key);
	});

	it.each(Object.keys(answerFormats) as AnswerFormatKey[])('%s gives an input the schema accepts', (key) => {
		const formatted = withAnswerFormat(typed, key);
		expect(formatted.state_type === 'input' && answerDefinitionSchema.safeParse(formatted.schema).success).toBe(true);
	});
});

describe('formatsFor', () => {
	it('offers contact formats on a Formatted question and ID formats on the ID questions', () => {
		const offered = (key: 'formatted_question' | 'data_question' | 'data_decision') => {
			const added = addModule(journey, key);
			return formatsFor(added.process.states[added.first]);
		};
		expect(offered('formatted_question')).toContain('email');
		expect(offered('data_question')).toContain('national_insurance_number');
		expect(offered('data_decision')).toEqual(offered('data_question'));
	});

	it('offers nothing on an input that did not come from a module that names formats', () => {
		expect(formatsFor(typed)).toEqual([]);
		const added = addModule(journey, 'simple_question');
		expect(formatsFor(added.process.states[added.first])).toEqual([]);
	});
});

describe('withAnswerFormat', () => {
	it('fills in the pattern, message and tidying of the format, and writes the format as the answer type', () => {
		const formatted = withAnswerFormat(typed, 'email');
		expect(formatted.state_type === 'input' && formatted.schema).toEqual({
			kind: 'string',
			pattern: answerFormats.email.pattern,
			invalid_message: answerFormats.email.invalidMessage,
			normalise: 'lower_trim'
		});
		expect(formatted.metadata?.[answerTypeKey]).toBe('email');
		expect(answerFormatOf(formatted)).toBe('email');
	});

	it('keeps an answer type that has no format, such as name, when no format is chosen', () => {
		const named: WorkingState = { ...typed, metadata: { [answerTypeKey]: 'name' } };
		expect(withAnswerFormat(named, undefined).metadata?.[answerTypeKey]).toBe('name');
		expect(answerFormatOf(named)).toBeUndefined();
	});

	it('takes the tidying away when the new format has none', () => {
		const changed = withAnswerFormat(withAnswerFormat(typed, 'email'), 'phone_number');
		expect(changed.state_type === 'input' && changed.schema).not.toHaveProperty('normalise');
	});

	it('takes everything away when no format is chosen', () => {
		const cleared = withAnswerFormat(withAnswerFormat(typed, 'email'), undefined);
		expect(cleared.state_type === 'input' && cleared.schema).toEqual({ kind: 'string' });
		expect(cleared.metadata).toBeUndefined();
	});
});
