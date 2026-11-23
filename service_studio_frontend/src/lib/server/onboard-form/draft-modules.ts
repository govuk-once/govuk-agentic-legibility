import { isEditableInForm } from '$lib/form-editor/schema/form-states';
import { moduleTileFor } from '$lib/modules/module-catalogue';
import { shapesOfModule } from '$lib/modules/module-copies';
import { moduleDefinitions, type ModuleKey } from '$lib/modules/module-states';

/*
	The modules a drafted form may be built from.

	1. A drafted form only asks questions, shows messages and decides, so it may only use modules made of states a
	   person edits in the form editor. Modules with a call, a wait or an assign, such as Submit or Many answers, are
	   added by the person in the editor when the form needs them.
	2. Of those, it only uses the modules that give a state something it would not have on its own: a format to check
	   the answer against, or more than one state, such as a question and the decision on its answer. A plain question
	   or message is written as a state on its own.
*/

// The key of every module a drafted form may use, in the order of the module menu's data.
export const draftFormModuleKeys: ModuleKey[] = (Object.keys(moduleDefinitions) as ModuleKey[]).filter((key) => {
	const definition = moduleDefinitions[key];
	const states = Object.values(definition.build((part) => part).states);
	return states.every(isEditableInForm) && (states.length > 1 || definition.answerFormats !== undefined);
});

/**
 * Tells whether a drafted form may use a module.
 */
export function isDraftFormModule(key: ModuleKey): boolean {
	return draftFormModuleKeys.includes(key);
}

/**
 * Describes a module for the model in one line: its key and name, what it is for, the states it is made of in order,
 * and what the model must write in them, all read from the module itself so the description never drifts from it.
 */
export function describeDraftModule(key: ModuleKey): string {
	const tile = moduleTileFor(key);
	const definition = moduleDefinitions[key];
	const states = Object.values(definition.build((part) => part).states);

	const question = states.find((state) => state.state_type === 'input');
	const decision = states.find((state) => state.state_type === 'choice');
	const end = states.find((state) => state.state_type === 'end');
	const tests = decision?.state_type === 'choice' ? [...new Set(decision.rules.map((rule) => rule.when.op))].join(' or ') : undefined;

	return [
		`- ${key} (${tile?.label ?? key}): ${tile?.description ?? ''}. Its states, in order: ${shapesOfModule(key).join(', then ')}.`,
		question?.state_type === 'input' && question.schema.allow_skip ? 'The question has allow_skip true, so it can be left blank.' : '',
		tests ? `The choice tests the answer to the question with ${tests}.` : '',
		definition.answerFormats ? `The question's answer_type is one of: ${definition.answerFormats.join(', ')}.` : '',
		end?.state_type === 'end' ? `The end has status ${end.status}.` : ''
	]
		.filter(Boolean)
		.join(' ');
}
