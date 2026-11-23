import { editableOptions } from '$lib/schema/workflow/answer-options';
import { conditionForAnswer } from '$lib/schema/workflow/choice-answers';
import { replaceState } from '$lib/schema/workflow/edit-state';
import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
import { isModuleKey } from './add-module';
import { isInModule, statesOfSameModule } from './module-group';
import { moduleDefinitions } from './module-states';

/*
	Adds a way out to the decision of a module when an option is added to its input, so every option has its own
	route and two options never share one without the person noticing.

	1. Only a module whose definition says so does this, such as the Choice decision. The editor reads the setting
	   from the module, so a new module of this kind needs no change here.
	2. The decision is the one in the same copy of the module, found by its group id, so a second copy of the module
	   or a decision drawn by hand is never changed.
	3. Each new way out is left loose, for the person to join. Removing an option does not remove its way out, so
	   nothing the person joined is lost, and the check before owner review finds a way out that leads nowhere.
*/

/**
 * Adds a loose way out to the decision of a module for each option the edited input gains. The process is
 * returned as it was when the input is not part of such a module or gained no options.
 */
export function withRoutesForNewOptions(process: WorkingProcess, code: string, updated: WorkingState): WorkingProcess {
	const before = process.states[code];
	const group = before?.metadata?.group;
	if (updated.state_type !== 'input' || typeof group !== 'string' || !isModuleKey(group)) return process;
	if (!moduleDefinitions[group].addsRoutesForOptions || !isInModule(before)) return process;

	const known = new Set((editableOptions(before) ?? []).map((option) => option.value));
	const added = (editableOptions(updated) ?? []).filter((option) => !known.has(option.value));
	const decisionCode = statesOfSameModule(process, code).find((each) => process.states[each].state_type === 'choice');
	const decision = decisionCode === undefined ? undefined : process.states[decisionCode];
	if (added.length === 0 || decisionCode === undefined || decision?.state_type !== 'choice') return process;

	const rules = added.flatMap((option) => {
		const when = conditionForAnswer(updated, option.value);
		return when ? [{ when }] : [];
	});
	return replaceState(process, decisionCode, { ...decision, rules: [...decision.rules, ...rules] });
}
