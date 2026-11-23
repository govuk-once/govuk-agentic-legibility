import { describe, expect, it } from 'vitest';
import { formExamples } from '$lib/examples/forms';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { moduleCopyProblems } from '../module-copies';

// The form examples made of modules, each with its one process.
const moduleForms = formExamples
	.filter((example) => example.slug.endsWith('_with_modules'))
	.flatMap((example): { slug: string; process: WorkingProcess }[] => {
		const [process] = Object.values(example.workflow?.processes ?? {});
		return process ? [{ slug: example.slug, process }] : [];
	});

describe('the form examples made of modules', () => {
	it('has the three examples', () => {
		expect(moduleForms.map((form) => form.slug).sort()).toEqual([
			'2026_bft_crrf_additional_trainer_information_with_modules',
			'add_funds_to_your_intellectual_property_office_deposit_account_with_modules',
			'amend_my_claim_for_unpaid_wages_with_modules'
		]);
	});

	it('marks every copy of a module with a module key, and gives it the same shape as the module', () => {
		for (const { slug, process } of moduleForms) expect(moduleCopyProblems(process), slug).toEqual([]);
	});

	it('sends from Submit only the answers that a step in the form saves', () => {
		const trainer = moduleForms.find((form) => form.slug.startsWith('2026_bft'))!.process;
		const saved = Object.values(trainer.states).flatMap((state) => {
			if (state.state_type === 'input') return [state.assign];
			if (state.state_type === 'assign') return Object.keys(state.set);
			return [];
		});
		const submit = trainer.states.submit;
		// Each value Submit sends is written as {"$": name}, which names the answer to send.
		const sent = submit.state_type === 'api_call' ? Object.values(submit.body ?? {}).flatMap((value) => (value && typeof value === 'object' && '$' in value ? [value.$] : [])) : [];

		expect(sent).toEqual(['answers.applicant_name', 'answers.vessel_name', 'answers.additional_trainers']);
		for (const name of sent) expect(saved).toContain(name);
	});
});
