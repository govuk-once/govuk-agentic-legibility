import { describe, expect, it } from 'vitest';
import { describeDraftModule, draftFormModuleKeys, isDraftFormModule } from '../draft-modules';

describe('draftFormModuleKeys', () => {
	it('offers the modules that add a format or a decision, made only of states a person edits in a form', () => {
		expect(draftFormModuleKeys).toEqual(['formatted_question', 'data_question', 'choice_decision', 'boolean_decision', 'data_decision', 'information']);
	});

	it('leaves out the modules a person adds by hand, such as Submit and Many answers', () => {
		for (const key of ['submit', 'many_answers', 'wait', 'user_details'] as const) expect(isDraftFormModule(key), key).toBe(false);
	});
});

describe('describeDraftModule', () => {
	it('names the states of a module in order, and how its decision tests the answer', () => {
		expect(describeDraftModule('boolean_decision')).toBe(
			'- boolean_decision (Yes / No): Route by yes or no. Its states, in order: input with a boolean answer, then choice. The choice tests the answer to the question with is_true.'
		);
	});

	it('names the answer types a question with a format may have, and a question that can be left blank', () => {
		const line = describeDraftModule('data_decision');
		expect(line).toContain('allow_skip true');
		expect(line).toContain('not_empty');
		expect(line).toContain('national_insurance_number');
	});

	it('names the status of the end a module finishes with, such as offramp for Information', () => {
		expect(describeDraftModule('information')).toContain('The end has status offramp.');
	});
});
