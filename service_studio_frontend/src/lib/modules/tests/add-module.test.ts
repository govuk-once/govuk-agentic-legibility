import { describe, expect, it } from 'vitest';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { addModule, isModuleKey } from '../add-module';

// A journey with one message and nothing else, to add modules to.
const journey: WorkingProcess = {
	process_id: 'test',
	version: '0.1.0',
	start: 'hello',
	vars: {},
	states: { hello: { state_type: 'output', channel: 'transcript', message: 'Hello' } }
};

describe('isModuleKey', () => {
	it('knows the key of a module that adds states, and not a basic shape or anything else', () => {
		expect(isModuleKey('boolean_decision')).toBe(true);
		expect(isModuleKey('input')).toBe(false);
		expect(isModuleKey('toString')).toBe(false);
	});
});

describe('addModule', () => {
	it('adds every state of the module, named by the module and its part, and leaves the rest of the journey alone', () => {
		const added = addModule(journey, 'boolean_decision');
		expect(added.codes).toEqual(['boolean_decision_ask', 'boolean_decision_decide']);
		expect(added.first).toBe('boolean_decision_ask');
		expect(added.process.start).toBe('hello');
		expect(added.process.states.hello).toBe(journey.states.hello);
	});

	it('marks every state with the module key and one random code shared by the whole copy', () => {
		const added = addModule(journey, 'submit');
		const groups = added.codes.map((code) => added.process.states[code].metadata);
		for (const metadata of groups) expect(metadata?.group).toBe('submit');
		expect(new Set(groups.map((metadata) => metadata?.group_id)).size).toBe(1);
		expect(groups[0]?.group_id).toEqual(expect.any(String));
	});

	it('gives a second copy the same number on every part and a different random code', () => {
		const first = addModule(journey, 'boolean_decision');
		const second = addModule(first.process, 'boolean_decision');
		expect(second.codes).toEqual(['boolean_decision_ask_2', 'boolean_decision_decide_2']);
		expect(second.process.states.boolean_decision_ask_2.metadata?.group_id).not.toBe(
			first.process.states.boolean_decision_ask.metadata?.group_id
		);
	});

	it('joins the second copy to its own states and not to the first copy', () => {
		const second = addModule(addModule(journey, 'boolean_decision').process, 'boolean_decision');
		const ask = second.process.states.boolean_decision_ask_2;
		expect(ask.state_type === 'input' && ask.next).toBe('boolean_decision_decide_2');
		expect(ask.state_type === 'input' && ask.assign).not.toBe('answer_boolean_decision_ask');
	});

	it('does not join the module to the rest of the journey', () => {
		const added = addModule(journey, 'message');
		expect(added.process.states.hello).not.toHaveProperty('next');
		expect(added.process.states[added.first]).not.toHaveProperty('next');
	});
});
