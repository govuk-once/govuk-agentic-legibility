import { describe, expect, it } from 'vitest';
import { descriptionKey } from '$lib/schema/workflow/edit-state';
import { undecidedRule, unconnectedApiCallDetails } from '$lib/schema/workflow/placeholders';
import { parseProcess } from '$lib/schema/workflow/validate';
import { firstVersion } from '../build-workflow';
import { SERVICE_SYSTEM_PROMPT } from '../system-prompt';

// The instructions come first and the JSON Schema is added after this line, so the two can be read separately.
const schemaIntro = 'The JSON you reply with must validate against this JSON Schema:';
const [instructions, schemaText] = SERVICE_SYSTEM_PROMPT.split(schemaIntro);

describe('SERVICE_SYSTEM_PROMPT', () => {
	it('ends with a JSON Schema that can be read and describes a process', () => {
		const schema = JSON.parse(schemaText.trim());
		expect(schema.type).toBe('object');
		expect(schema.required).toEqual(expect.arrayContaining(['process_id', 'version', 'start', 'states']));
	});

	it('names the placeholder values from the shared constants, so the model writes what the app recognises', () => {
		expect(instructions).toContain(JSON.stringify(undecidedRule));
		expect(instructions).toContain(JSON.stringify(unconnectedApiCallDetails));
		expect(instructions).toContain(`"${descriptionKey}"`);
		expect(instructions).toContain(`"${firstVersion}"`);
	});

	it('asks for the states this route uses and no others', () => {
		expect(instructions).toContain('input, output, api_call, choice and\nend');
		for (const unused of ['invoke', 'wait', 'assign state']) expect(instructions).not.toContain(unused);
	});

	it('tells the model to leave out error routes and timeouts, which the app adds', () => {
		expect(instructions).toContain('Do not write error routes or timeouts');
		for (const key of ['catch', 'on_invalid', 'timeout', 'timeouts', 'retry']) expect(instructions).toContain(key);
	});

	it('does not ask the model for the owner, ids or other details the app fills in', () => {
		expect(instructions).toContain('added afterwards');
		expect(instructions).not.toMatch(/startStepId|descriptionPublic|\bUUID for every\b/);
	});

	it('gives a placeholder condition and call that pass the process checks', () => {
		// A journey written the way the prompt describes: a question, a decision on its answer, a placeholder call, an end.
		const process = {
			process_id: 'main',
			version: firstVersion,
			start: 'ask',
			vars: {},
			states: {
				ask: { type: 'input', name: 'Ask', prompt: 'Yes or no?', schema: { kind: 'boolean' }, assign: 'answer', next: 'decide' },
				decide: { type: 'choice', rules: [{ when: { ...undecidedRule }, next: 'look_up' }], default: 'finish' },
				look_up: { type: 'api_call', ...unconnectedApiCallDetails, next: 'finish' },
				finish: { type: 'end', status: 'success' }
			}
		};
		const result = parseProcess(process);
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
	});
});
