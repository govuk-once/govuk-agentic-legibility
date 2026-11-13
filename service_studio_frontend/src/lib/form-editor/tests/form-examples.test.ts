import { describe, expect, it } from 'vitest';
import { formExampleFolders, formExamples } from '$lib/examples/forms';
import { checkBeforeProceeding } from '$lib/schema/workflow/validate';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { checkFormWorkflow, formStateAccess } from '../schema/form-states';

// The forms that loaded. A form that failed to load would already fail the tests of the examples themselves.
const forms = formExamples.flatMap((example) => (example.workflow ? [{ slug: example.slug, workflow: example.workflow }] : []));
const statesOf = (workflow: Workflow) => Object.values(workflow.processes).flatMap((process) => Object.entries(process.states));

describe('the form examples, as the form editor sees them', () => {
	it('has all 14 forms loaded', () => {
		expect(forms).toHaveLength(14);
	});

	it('gives every form a single process, which is what the form editor opens', () => {
		for (const { slug, workflow } of forms) expect(checkFormWorkflow(workflow), slug).toEqual([]);
	});

	it('is complete enough to pass the check before proceeding, with nothing unjoined or unfinished', () => {
		for (const { slug, workflow } of forms) expect(checkBeforeProceeding(workflow), slug).toEqual([]);
	});

	it('only uses kinds of state that the form editor knows how to treat', () => {
		const known = Object.keys(formStateAccess);
		for (const { slug, workflow } of forms) {
			for (const [code, state] of statesOf(workflow)) expect(known, `${slug}: ${code}`).toContain(state.state_type);
		}
	});

	it('uses the states that forms are made of, with one assign for the one repeated question', () => {
		const counts: Record<string, number> = {};
		for (const { workflow } of forms) for (const [, state] of statesOf(workflow)) counts[state.state_type] = (counts[state.state_type] ?? 0) + 1;
		expect(counts).toEqual({ input: 211, choice: 43, output: 28, end: 28, assign: 1 });
	});
});

describe('how the form files are read', () => {
	const rawStates = Object.values(formExampleFolders).flatMap((files) =>
		Object.entries(files)
			.filter(([name]) => name !== 'workflow_manifest.json')
			.flatMap(([, process]) => Object.values((process as { states: Record<string, Record<string, unknown>> }).states))
	);

	it('writes the kind of state as type in the files, which is the alias', () => {
		expect(rawStates).toHaveLength(311);
		for (const state of rawStates) {
			expect(state).toHaveProperty('type');
			expect(state).not.toHaveProperty('state_type');
		}
	});

	it('reads every state as state_type, and none keeps the alias', () => {
		for (const { slug, workflow } of forms) {
			for (const [code, state] of statesOf(workflow)) {
				expect(state, `${slug}: ${code}`).toHaveProperty('state_type');
				expect(state, `${slug}: ${code}`).not.toHaveProperty('type');
			}
		}
	});

	it('keeps the notes of a question exactly as the file has them, including the nested answer settings', () => {
		const raw = Object.values(formExampleFolders.allergen_and_ingredients_food_labelling_decision_tool).find((file) => 'states' in (file as object)) as {
			states: Record<string, { metadata: unknown }>;
		};
		const loaded = forms.find((form) => form.slug === 'allergen_and_ingredients_food_labelling_decision_tool')!.workflow;
		const process = Object.values(loaded.processes)[0];
		expect(process.states.step_1.metadata).toEqual(raw.states.step_1.metadata);
		expect(process.states.step_1.metadata).toHaveProperty('answer_settings.selection_options');
	});

	it('has no owner, because the files leave it out, and does not fill one in', () => {
		for (const { slug, workflow } of forms) expect('owner' in workflow.manifest, slug).toBe(false);
	});

	it('says Workflow/0.2 in every manifest', () => {
		for (const { slug, workflow } of forms) expect(workflow.manifest.schema, slug).toBe('Workflow/0.2');
	});
});

describe('the one question that is asked more than once', () => {
	const form = forms.find((candidate) => candidate.slug === '2026_bft_crrf_additional_trainer_information')!;
	const groupOf = (state: { metadata?: Record<string, unknown> }) => state.metadata?.group;

	it('has the four states of its add another answer block in one group, named in plain words', () => {
		const process = Object.values(form.workflow.processes)[0];
		const grouped = Object.entries(process.states).filter(([, state]) => groupOf(state) !== undefined);

		expect(grouped.map(([code]) => code).sort()).toEqual(['step_3', 'step_3_append', 'step_3_more', 'step_3_repeat_route']);
		for (const [, state] of grouped) expect(groupOf(state)).toBe('Add another answer');
	});

	it('is the only group in all of the forms', () => {
		const grouped = forms.flatMap(({ workflow }) => statesOf(workflow).filter(([, state]) => groupOf(state) !== undefined));
		expect(grouped).toHaveLength(4);
	});

	it('is the only form with an assign', () => {
		const withAssign = forms.filter(({ workflow }) => statesOf(workflow).some(([, state]) => state.state_type === 'assign'));
		expect(withAssign.map((candidate) => candidate.slug)).toEqual(['2026_bft_crrf_additional_trainer_information']);
	});
});
