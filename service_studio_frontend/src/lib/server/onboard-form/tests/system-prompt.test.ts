import { describe, expect, it } from 'vitest';
import { answerFormats } from '$lib/modules/answer-formats';
import { answerTypeKey, answerTypesByKind } from '$lib/schema/workflow/answer-types';
import { descriptionKey, hintKey } from '$lib/schema/workflow/edit-state';
import { undecidedRule } from '$lib/schema/workflow/placeholders';
import { parseProcess } from '$lib/schema/workflow/validate';
import { firstVersion } from '$lib/server/shared/onboard-details';
import { schemaIntro } from '$lib/server/shared/process-json-schema';
import { statesNotForForms } from '$lib/server/onboard-form/build-form';
import { describeDraftModule, draftFormModuleKeys } from '$lib/server/onboard-form/draft-modules';
import { FORM_SYSTEM_PROMPT } from '$lib/server/onboard-form/system-prompt';

// The instructions come first and the JSON Schema is added after the intro, so the two can be read separately.
const [instructions, schemaText] = FORM_SYSTEM_PROMPT.split(schemaIntro);

describe('FORM_SYSTEM_PROMPT', () => {
	it('ends with a JSON Schema that can be read and describes a process', () => {
		const schema = JSON.parse(schemaText.trim());
		expect(schema.type).toBe('object');
		expect(schema.required).toEqual(expect.arrayContaining(['process_id', 'version', 'start', 'states']));
	});

	it('asks for the states a form has and no others', () => {
		expect(instructions).toContain('The only state types to use are input, output, choice and end.');
		for (const unused of ['api_call', 'assign state', 'invoke', 'wait state']) expect(instructions).not.toContain(unused);
	});

	it('names the notes and the placeholder rule from the shared constants, so the model writes what the app recognises', () => {
		for (const key of [descriptionKey, hintKey, answerTypeKey]) expect(instructions).toContain(`"${key}"`);
		expect(instructions).toContain(JSON.stringify(undecidedRule));
		expect(instructions).toContain(`"${firstVersion}"`);
	});

	it('names every answer type the app recognises', () => {
		for (const type of Object.values(answerTypesByKind).flat()) expect(instructions, type).toContain(type);
	});

	it('lists every module a drafted form may use, as each module describes itself, and no other', () => {
		for (const key of draftFormModuleKeys) expect(instructions).toContain(describeDraftModule(key));
		for (const key of ['submit', 'many_answers']) expect(instructions).not.toContain(`- ${key} (`);
		expect(instructions).toContain('"group_id"');
	});

	it('names the answer types that come with a format, and tells the model not to write a pattern', () => {
		for (const key of Object.keys(answerFormats)) expect(instructions).toContain(key);
		expect(instructions).toContain('Do not write a\npattern or an invalid_message yourself');
	});

	it('asks for answer names under answers, and titles that do not copy the question', () => {
		expect(instructions).toContain('answers.applicant_full_name');
		expect(instructions).toContain('Do not copy the question or the message into the title');
	});

	it('tells the model to leave out error routes and timeouts', () => {
		expect(instructions).toContain('Do not write error routes or timeouts');
		for (const key of ['catch', 'on_invalid', 'timeout', 'timeouts', 'retry']) expect(instructions).toContain(key);
	});

	it('does not ask the model for the owner, ids or other details the app fills in', () => {
		expect(instructions).toContain('added afterwards');
	});

	it('describes a form that passes the process checks and has only states a form can have', () => {
		// A form written the way the prompt describes: a message, a question, a decision on its answer and two ends.
		const process = {
			process_id: 'main',
			version: firstVersion,
			start: 'declaration',
			vars: {},
			states: {
				declaration: { state_type: 'output', name: 'Declaration', channel: 'transcript', message: 'Read this first.', next: 'accept' },
				accept: {
					state_type: 'input',
					name: 'Accept',
					metadata: { [descriptionKey]: 'Asks for agreement.', [answerTypeKey]: 'selection', [hintKey]: 'Choose yes to continue.' },
					prompt: 'Do you accept?',
					schema: { kind: 'boolean' },
					assign: 'accepted',
					next: 'decide'
				},
				decide: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'accepted' }, next: 'finish' }], default: 'declined' },
				finish: { state_type: 'end', status: 'success' },
				declined: { state_type: 'end', status: 'cancelled' }
			}
		};
		const result = parseProcess(process);
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
		if (result.ok) expect(statesNotForForms(result.process)).toEqual([]);
	});
});
