import { describe, expect, it } from 'vitest';
import { deleteFromJourney } from '$lib/schema/workflow/remove-state';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { addModule } from '$lib/modules/add-module';
import { isInModule, statesOfSameModule } from '$lib/modules/module-group';

const journey: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'hello', vars: {}, states: { hello: { state_type: 'output', channel: 'transcript', message: 'Hello' } } };

describe('isInModule', () => {
	it('tells a state added with a module from one that was not', () => {
		const { process } = addModule(journey, 'boolean_decision');
		expect(isInModule(process.states.boolean_decision_ask)).toBe(true);
		expect(isInModule(process.states.hello)).toBe(false);
	});
});

describe('statesOfSameModule', () => {
	it('lists every state of the same copy of a module, whichever of them is given', () => {
		const { process } = addModule(journey, 'many_answers');
		const all = ['many_answers_ask', 'many_answers_keep', 'many_answers_more', 'many_answers_again'];
		expect(statesOfSameModule(process, 'many_answers_keep').sort()).toEqual([...all].sort());
	});

	it('leaves out a second copy of the same module', () => {
		const twice = addModule(addModule(journey, 'boolean_decision').process, 'boolean_decision').process;
		expect(statesOfSameModule(twice, 'boolean_decision_decide_2').sort()).toEqual(['boolean_decision_ask_2', 'boolean_decision_decide_2']);
	});

	it('lists a state that was not added with a module on its own', () => {
		expect(statesOfSameModule(journey, 'hello')).toEqual(['hello']);
	});

	it('gives the states that removing one of them takes out, leaving the rest of the journey', () => {
		const { process } = addModule(journey, 'boolean_decision');
		const removed = deleteFromJourney(process, { stateCodes: statesOfSameModule(process, 'boolean_decision_decide'), lines: [] });
		expect(removed.ok && Object.keys(removed.process.states)).toEqual(['hello']);
	});
});
