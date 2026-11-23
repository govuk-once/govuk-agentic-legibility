import { describe, expect, it } from 'vitest';
import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
import { addModule } from '../add-module';
import { moduleCopyProblems, shapesOfModule } from '../module-copies';

const journey: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'hello', vars: {}, states: { hello: { state_type: 'output', channel: 'transcript', message: 'Hello' } } };

// A process with one state changed, as a model might write it.
const withState = (process: WorkingProcess, code: string, state: WorkingState): WorkingProcess => ({ ...process, states: { ...process.states, [code]: state } });

describe('shapesOfModule', () => {
	it('lists the shapes of a module in the order they run', () => {
		expect(shapesOfModule('boolean_decision')).toEqual(['input with a boolean answer', 'choice']);
		expect(shapesOfModule('information')).toEqual(['output', 'end']);
	});
});

describe('moduleCopyProblems', () => {
	it('finds nothing wrong with modules that were dropped, or with states that are in no module', () => {
		const { process } = addModule(addModule(journey, 'boolean_decision').process, 'submit');
		expect(moduleCopyProblems(process)).toEqual([]);
	});

	it('names a copy whose states do not have the shapes of its module', () => {
		const { process } = addModule(journey, 'boolean_decision');
		const ask = process.states.boolean_decision_ask;
		if (ask.state_type !== 'input') throw new Error('The Yes / No module starts with an input');
		const wrong = withState(process, 'boolean_decision_ask', { ...ask, schema: { kind: 'select_one', options: [{ value: 'a', label: 'A' }] } });

		const [problem] = moduleCopyProblems(wrong);
		expect(problem.message).toContain('must be made of: input with a boolean answer, choice');
	});

	it('names a module that the caller does not allow, such as Submit in a drafted form', () => {
		const { process } = addModule(journey, 'submit');
		expect(moduleCopyProblems(process, (key) => key !== 'submit')).toHaveLength(1);
	});

	it('names a state that names a module but has no group id', () => {
		const lone = withState(journey, 'hello', { state_type: 'output', channel: 'transcript', message: 'Hello', metadata: { group: 'message' } });
		expect(moduleCopyProblems(lone)[0].path).toBe('states.hello.metadata.group_id');
	});

	it('names a copy whose states name different modules', () => {
		const mixed = withState(withState(journey, 'a', { state_type: 'output', channel: 'transcript', message: 'A', metadata: { group: 'message', group_id: 'x' } }), 'b', {
			state_type: 'output',
			channel: 'transcript',
			message: 'B',
			metadata: { group: 'start_page', group_id: 'x' }
		});
		expect(moduleCopyProblems(mixed)[0].message).toContain('name different modules');
	});
});
