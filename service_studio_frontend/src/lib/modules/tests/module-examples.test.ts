import { describe, expect, it } from 'vitest';
import { formExamples } from '$lib/examples/forms';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { isModuleKey } from '../add-module';
import { moduleDefinitions } from '../module-states';

// The form examples made of modules, each with its one process.
const moduleForms = formExamples
	.filter((example) => example.slug.endsWith('_with_modules'))
	.flatMap((example): { slug: string; process: WorkingProcess }[] => {
		const [process] = Object.values(example.workflow?.processes ?? {});
		return process ? [{ slug: example.slug, process }] : [];
	});

// The kinds of state a module adds, sorted, so a copy in an example can be compared with the module itself.
const typesOfModule = (key: string) =>
	isModuleKey(key) ? Object.values(moduleDefinitions[key].build((part) => part).states).map((state) => state.state_type).sort() : [];

describe('the form examples made of modules', () => {
	it('has the three examples', () => {
		expect(moduleForms.map((form) => form.slug).sort()).toEqual([
			'2026_bft_crrf_additional_trainer_information_with_modules',
			'add_funds_to_your_intellectual_property_office_deposit_account_with_modules',
			'amend_my_claim_for_unpaid_wages_with_modules'
		]);
	});

	it('marks every copy of a module with a module key, and gives it the same kinds of state as the module', () => {
		for (const { slug, process } of moduleForms) {
			const copies = new Map<string, { key: unknown; types: string[] }>();
			for (const state of Object.values(process.states)) {
				const groupId = state.metadata?.group_id;
				if (typeof groupId !== 'string') continue;
				const copy = copies.get(groupId) ?? { key: state.metadata?.group, types: [] };
				copy.types.push(state.state_type);
				copies.set(groupId, copy);
			}
			expect(copies.size, slug).toBeGreaterThan(0);
			for (const [groupId, copy] of copies) {
				expect(typeof copy.key === 'string' && isModuleKey(copy.key), `${slug}: ${groupId}`).toBe(true);
				expect(copy.types.sort(), `${slug}: ${copy.key}`).toEqual(typesOfModule(String(copy.key)));
			}
		}
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
