import { describe, expect, it } from 'vitest';
import { stateUnionSchema } from '$lib/schema/workflow/process';
import { routesOf } from '$lib/schema/workflow/routes';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import { basicCategories, moduleCategories } from '../module-catalogue';
import { moduleDefinitions, type ModuleKey } from '../module-states';

// Every module in the menu that is not a basic shape, so a module added to the menu without its states is noticed.
const basicKeys = new Set<string>(basicCategories.flatMap((category) => category.modules.map((module) => module.key)));
const menuModuleKeys = moduleCategories.flatMap((category) => category.modules.map((module) => module.key)).filter((key) => !basicKeys.has(key));
const definedKeys = Object.keys(moduleDefinitions) as ModuleKey[];

// Builds a module with each part named after itself, or after itself with a suffix to stand in for a second copy.
const build = (key: ModuleKey, suffix = '') => moduleDefinitions[key].build((part) => `${part}${suffix}`);

// Gives every loose route a target outside the module, so a state can be checked against the strict schema that a
// saved journey must match.
function joined(state: WorkingState): unknown {
	if (state.state_type === 'end') return state;
	if (state.state_type === 'choice') {
		return { ...state, rules: state.rules.map((rule) => ({ ...rule, next: rule.next ?? 'outside' })), default: state.default ?? 'outside' };
	}
	return { ...state, next: state.next ?? 'outside' };
}

describe('moduleDefinitions', () => {
	it('has states for every module in the menu that is not a basic shape, and no others', () => {
		expect([...definedKeys].sort()).toEqual([...menuModuleKeys].sort());
	});

	it.each(definedKeys)('%s begins at one of its own states', (key) => {
		const { first, states } = build(key);
		expect(states).toHaveProperty(first);
	});

	it.each(definedKeys)('%s only routes to its own states, leaving every other route loose', (key) => {
		const { states } = build(key);
		for (const state of Object.values(states)) {
			for (const route of routesOf(state)) expect(states, `route to ${route.target}`).toHaveProperty(route.target);
		}
	});

	it.each(definedKeys)('%s makes states that are valid once their loose routes are joined', (key) => {
		for (const state of Object.values(build(key).states)) expect(stateUnionSchema.safeParse(joined(state)).success).toBe(true);
	});

	it.each(definedKeys)('%s saves its answers in different variables when it is added a second time', (key) => {
		const savedIn = (states: Record<string, WorkingState>) =>
			Object.values(states).flatMap((state) => (state.state_type === 'input' ? [state.assign] : []));
		const first = savedIn(build(key).states);
		const second = savedIn(build(key, '_2').states);
		for (const variable of second) expect(first).not.toContain(variable);
	});
});

describe('the modules as the executor team gave them', () => {
	const typesOf = (key: ModuleKey) => Object.values(build(key).states).map((state) => state.state_type);

	it('asks a single question in each Ask module, with the answer kind it is for', () => {
		const kindOf = (key: ModuleKey) => {
			const [state] = Object.values(build(key).states);
			return state.state_type === 'input' ? state.schema.kind : undefined;
		};
		expect(kindOf('simple_question')).toBe('string');
		expect(kindOf('boolean_question')).toBe('boolean');
		expect(kindOf('select_one')).toBe('select_one');
		expect(kindOf('select_many')).toBe('select_many');
	});

	it('starts Select one with two placeholder options and Select many with three', () => {
		const optionsOf = (key: ModuleKey) => {
			const [state] = Object.values(build(key).states);
			return state.state_type === 'input' && 'options' in state.schema ? state.schema.options : undefined;
		};
		expect(optionsOf('select_one')).toEqual([
			{ value: 'option_1', label: 'Option 1' },
			{ value: 'option_2', label: 'Option 2' }
		]);
		expect(optionsOf('select_many')).toHaveLength(3);
	});

	it('loops Many answers back to its question when the person adds another', () => {
		const { first, states } = build('many_answers');
		expect(typesOf('many_answers')).toEqual(['input', 'assign', 'input', 'choice']);
		const loop = Object.values(states).find((state) => state.state_type === 'choice');
		expect(loop?.state_type === 'choice' && loop.rules[0].next).toBe(first);
	});

	it('leaves every route out of a decision module loose', () => {
		for (const key of ['choice_decision', 'boolean_decision', 'data_decision'] as const) {
			expect(typesOf(key)).toEqual(['input', 'choice']);
			const decision = Object.values(build(key).states)[1];
			expect(routesOf(decision)).toEqual([]);
		}
	});

	it('titles the decision of every decision module Question decision', () => {
		for (const key of ['choice_decision', 'boolean_decision', 'data_decision'] as const) {
			const decision = Object.values(build(key).states)[1];
			expect(decision.name).toBe('Question decision');
		}
	});

	it('lets the question of a Data decision be left blank and routes on whether it was answered', () => {
		const [question, decision] = Object.values(build('data_decision').states);
		expect(question.state_type === 'input' && question.schema.allow_skip).toBe(true);
		expect(decision.state_type === 'choice' && decision.rules[0].when.op).toBe('not_empty');
	});

	it('marks only the Choice decision as adding a route for each new option', () => {
		const marked = definedKeys.filter((key) => moduleDefinitions[key].addsRoutesForOptions);
		expect(marked).toEqual(['choice_decision']);
	});

	it('builds Submit as the trainer example does, with both calls failing to one end', () => {
		expect(typesOf('submit')).toEqual(['api_call', 'output', 'wait', 'api_call', 'choice', 'end', 'end']);
		const ends = Object.values(build('submit').states).filter((state) => state.state_type === 'end');
		expect(ends.map((end) => end.state_type === 'end' && end.status).sort()).toEqual(['failed', 'success']);
	});

	it('sends the person offline at the end of Information', () => {
		const end = Object.values(build('information').states).find((state) => state.state_type === 'end');
		expect(end?.state_type === 'end' && end.status).toBe('offramp');
	});

	it('builds the Deadline, Phone call and Letter modules as a message, a wait, a question and a message', () => {
		for (const key of ['deadline', 'phone_call', 'letter'] as const) expect(typesOf(key)).toEqual(['output', 'wait', 'input', 'output']);
	});
});
