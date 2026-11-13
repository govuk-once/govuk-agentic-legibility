import { describe, expect, it } from 'vitest';
import { stateUnionSchema } from '$lib/schema/workflow/process';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { checkFormWorkflow, formDeveloperStateTypes, formStateAccess, isEditableInForm } from '../schema/form-states';

const stateTypes = stateUnionSchema.options.map((option) => option.shape.state_type.value);

// A state with only the key the rules read. The cast is needed because each test gives only the keys it uses.
const state = (type: string) => ({ state_type: type }) as unknown as WorkingState;

describe('formStateAccess', () => {
	it('says how a form treats every kind of state in the schema, and no others', () => {
		expect(Object.keys(formStateAccess).sort()).toEqual([...stateTypes].sort());
	});

	it('edits questions, messages, decisions and ends', () => {
		for (const type of ['input', 'output', 'choice', 'end'] as const) expect(formStateAccess[type]).toBe('editable');
	});

	it('shows assign, wait, invoke and api_call without editing them', () => {
		for (const type of ['assign', 'wait', 'invoke', 'api_call'] as const) expect(formStateAccess[type]).toBe('read only');
	});
});

describe('isEditableInForm', () => {
	it('is true for the kinds a form edits and false for the rest', () => {
		expect(stateTypes.filter((type) => isEditableInForm(state(type))).sort()).toEqual(['choice', 'end', 'input', 'output']);
	});
});

describe('formDeveloperStateTypes', () => {
	it('names only real kinds of state', () => {
		for (const type of formDeveloperStateTypes) expect(stateTypes).toContain(type);
	});

	it('starts with assign, which a person never edits', () => {
		expect(formDeveloperStateTypes).toEqual(['assign']);
		expect(formStateAccess.assign).toBe('read only');
	});
});

describe('checkFormWorkflow', () => {
	// Only the list of processes is read, so each test gives the manifest a list of that length.
	const workflowOf = (count: number) =>
		({ manifest: { processes: Array.from({ length: count }, (_, index) => ({ process_id: `p${index}`, version: '0.1.0' })) } }) as unknown as Workflow;

	it('has nothing to say about a workflow of one process', () => {
		expect(checkFormWorkflow(workflowOf(1))).toEqual([]);
	});

	it('says that a workflow of several processes is not a form, and how many it has', () => {
		expect(checkFormWorkflow(workflowOf(3))).toEqual([
			{ path: 'manifest.processes', message: 'A form is one process, but this workflow lists 3. The form editor opens a single process.' }
		]);
	});

	it('says the same about a workflow that lists none', () => {
		expect(checkFormWorkflow(workflowOf(0))).toHaveLength(1);
	});
});
