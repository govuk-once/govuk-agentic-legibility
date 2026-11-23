import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
import { moduleDefinitions, type ModuleKey } from './module-states';

/*
	Adds the states of a module to a journey when it is dropped onto the canvas.

	1. Every state the module adds is marked with the module it came from, in its metadata. The group is the key of
	   the module, such as boolean_decision, so the canvas can find its name in the module list. The group id is a
	   random code made once for this drop, so two copies of the same module can be told apart. It is never
	   renumbered, so it stays the same while the journey is edited.
	2. The codes of the states are the key of the module and the name of each part, such as boolean_decision_ask.
	   When the module is already in the journey, every part of the new copy is given the same number, such as
	   boolean_decision_ask_2 and boolean_decision_decide_2, so the parts of one copy are easy to pair up.
	3. The new states are not joined to the rest of the journey. The person draws the lines.
*/

/**
 * Tells whether a value handed over by a drop names a module that adds states.
 */
export function isModuleKey(value: string): value is ModuleKey {
	return Object.hasOwn(moduleDefinitions, value);
}

/**
 * Finds the first number that, added to the code of every part, gives codes that no state in the journey already
 * has. No number is added when the plain codes are free.
 */
function freeSuffix(process: WorkingProcess, codes: string[]): string {
	const isFree = (suffix: string) => codes.every((code) => !(`${code}${suffix}` in process.states));
	if (isFree('')) return '';

	let number = 2;
	while (!isFree(`_${number}`)) number += 1;
	return `_${number}`;
}

/**
 * Adds a copy of a module to the journey, with nothing joined to it yet. Returns the changed journey, the code of the
 * state the module begins at, and the codes of all its states.
 */
export function addModule(process: WorkingProcess, key: ModuleKey): { process: WorkingProcess; first: string; codes: string[] } {
	const definition = moduleDefinitions[key];

	// The module is built once with plain codes to learn the names of its parts, and then again with codes that are
	// free in this journey. The module itself decides its parts, so this is the one place they are listed.
	const plainCode = (part: string) => `${key}_${part}`;
	const suffix = freeSuffix(process, Object.keys(definition.build(plainCode).states));
	const built = definition.build((part) => `${plainCode(part)}${suffix}`);

	const group = { group: key, group_id: crypto.randomUUID() };
	const marked = Object.fromEntries(
		Object.entries(built.states).map(([code, state]): [string, WorkingState] => [code, { ...state, metadata: { ...state.metadata, ...group } }])
	);

	return { process: { ...process, states: { ...process.states, ...marked } }, first: built.first, codes: Object.keys(marked) };
}
