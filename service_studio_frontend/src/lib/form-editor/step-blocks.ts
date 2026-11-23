import { isInModule, statesOfSameModule } from '$lib/modules/module-group';
import { stepWithItsAssign } from '$lib/schema/workflow/edit-process';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';

/**
 * Lists the states that move together with a step when it is moved up or down the list of steps. A state that came
 * in with a module moves with every other state of that copy of the module, so no part of a module is left behind.
 * Any other step moves with the assign that saves an answer before it, when there is one.
 */
export function formStepBlock(process: WorkingProcess, code: string): string[] {
	return isInModule(process.states[code]) ? statesOfSameModule(process, code) : stepWithItsAssign(process, code);
}
