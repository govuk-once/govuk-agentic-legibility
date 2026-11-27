import { describe, expect, it } from 'vitest';
import { editableOptions, newOption, withOptions } from '$lib/schema/workflow/answer-options';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { addModule } from '$lib/modules/add-module';
import { withRoutesForNewOptions } from '$lib/modules/option-routes';

const journey: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'hello', vars: {}, states: { hello: { state_type: 'output', channel: 'transcript', message: 'Hello' } } };

// The input of a module with one more option added, as the input card hands it over.
function withAddedOption(process: WorkingProcess, code: string) {
	const input = process.states[code];
	const options = editableOptions(input) ?? [];
	return withOptions(input, [...options, newOption(options)]);
}

// The rules of the first decision in the process with the given code.
const rulesOf = (process: WorkingProcess, code: string) => {
	const state = process.states[code];
	return state.state_type === 'choice' ? state.rules : [];
};

describe('withRoutesForNewOptions', () => {
	it('adds a loose way out to the Choice decision for an added option, testing its value', () => {
		const { process } = addModule(journey, 'choice_decision');
		const changed = withRoutesForNewOptions(process, 'choice_decision_ask', withAddedOption(process, 'choice_decision_ask'));
		const rules = rulesOf(changed, 'choice_decision_decide');

		expect(rules).toHaveLength(2);
		expect(rules[1]).toEqual({ when: { op: 'eq', path: 'answer_choice_decision_ask', value: 'option_3' } });
	});

	it('changes only the decision of the same copy of the module', () => {
		const first = addModule(journey, 'choice_decision');
		const { process } = addModule(first.process, 'choice_decision');
		const changed = withRoutesForNewOptions(process, 'choice_decision_ask_2', withAddedOption(process, 'choice_decision_ask_2'));

		expect(rulesOf(changed, 'choice_decision_decide_2')).toHaveLength(2);
		expect(rulesOf(changed, 'choice_decision_decide')).toHaveLength(1);
	});

	it('adds nothing when no option was added, such as when a label was edited or an option removed', () => {
		const { process } = addModule(journey, 'choice_decision');
		const input = process.states.choice_decision_ask;
		const relabelled = withOptions(input, [{ value: 'option_1', label: 'Employed' }]);
		expect(withRoutesForNewOptions(process, 'choice_decision_ask', relabelled)).toBe(process);
	});

	it('adds nothing for a module that does not add routes for its options, such as Select one', () => {
		const { process } = addModule(journey, 'select_one');
		expect(withRoutesForNewOptions(process, 'select_one_step', withAddedOption(process, 'select_one_step'))).toBe(process);
	});
});
