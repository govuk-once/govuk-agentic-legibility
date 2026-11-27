import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
import { isModuleKey } from '$lib/modules/add-module';
import { moduleTileFor } from '$lib/modules/module-catalogue';
import { moduleDefinitions, type ModuleKey } from '$lib/modules/module-states';

/*
	Checks the copies of modules in a process against the modules themselves. A copy is every state that shares one
	group id. A copy made by dropping a module always matches, so this is for copies written by someone else, such as
	a form drafted by the model, which can mark states as a module and give them the wrong shape.

	1. A state's shape is its kind, with the kind of answer for a question, so a Yes / No module is a boolean input and
	   a choice. The routes are not compared, because the person joins them.
	2. Every state of a copy must name the same module, and a state that names a module must have a group id, so the
	   canvas can draw its border and it moves and is removed as one.
*/

export type ModuleCopyProblem = { path: string; message: string };

// The shape of a state as a module is compared by: its kind, and the kind of answer for a question.
function shapeOf(state: WorkingState): string {
	return state.state_type === 'input' ? `input with a ${state.schema.kind} answer` : state.state_type;
}

/**
 * Lists the shapes of the states a module adds, in the order they run, such as an input with a boolean answer and
 * then a choice for the Yes / No module.
 */
export function shapesOfModule(key: ModuleKey): string[] {
	return Object.values(moduleDefinitions[key].build((part) => part).states).map(shapeOf);
}

/**
 * Finds every copy of a module in a process that is not one the given test allows, or whose states do not have the
 * shapes of the module. An empty list means every copy matches.
 */
export function moduleCopyProblems(process: WorkingProcess, isAllowed: (key: ModuleKey) => boolean = () => true): ModuleCopyProblem[] {
	const copies = new Map<string, { first: string; keys: Set<unknown>; shapes: string[] }>();
	const problems: ModuleCopyProblem[] = [];

	for (const [code, state] of Object.entries(process.states)) {
		const groupId = state.metadata?.group_id;
		if (typeof groupId !== 'string') {
			if (state.metadata?.group !== undefined) problems.push({ path: `states.${code}.metadata.group_id`, message: 'A state that names a module must also have a group_id' });
			continue;
		}
		const copy = copies.get(groupId) ?? { first: code, keys: new Set(), shapes: [] };
		copy.keys.add(state.metadata?.group);
		copy.shapes.push(shapeOf(state));
		copies.set(groupId, copy);
	}

	for (const [groupId, copy] of copies) {
		const path = `states.${copy.first}.metadata.group`;
		const [key] = copy.keys;
		if (copy.keys.size > 1) {
			problems.push({ path, message: `The states with group_id "${groupId}" name different modules` });
		} else if (typeof key !== 'string' || !isModuleKey(key) || !isAllowed(key)) {
			problems.push({ path, message: `"${String(key)}" is not a module that can be used here` });
		} else {
			const expected = shapesOfModule(key);
			if ([...copy.shapes].sort().join(', ') !== [...expected].sort().join(', ')) {
				const label = moduleTileFor(key)?.label ?? key;
				problems.push({
					path,
					message: `The ${label} module with group_id "${groupId}" must be made of: ${expected.join(', ')}. It is made of: ${copy.shapes.join(', ')}`
				});
			}
		}
	}
	return problems;
}
