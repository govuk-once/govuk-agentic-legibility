import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';

/*
	Finds the states that came in with the same copy of a module, by the group id each one keeps in its metadata. A
	module is removed as one block, so a person never leaves part of a module behind, such as the decision of a
	Yes / No module without its question.
*/

/**
 * Tells whether a state was added with a module.
 */
export function isInModule(state: WorkingState | undefined): boolean {
	return typeof state?.metadata?.group_id === 'string';
}

/**
 * Lists the codes of every state in the same copy of a module as the given state, the state itself among them. A
 * state that was not added with a module is listed on its own.
 */
export function statesOfSameModule(process: WorkingProcess, code: string): string[] {
	const groupId = process.states[code]?.metadata?.group_id;
	if (typeof groupId !== 'string') return [code];
	return Object.keys(process.states).filter((each) => process.states[each].metadata?.group_id === groupId);
}
