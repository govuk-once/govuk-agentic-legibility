import { generateWorkflow, type GenerateDependencies, type GenerateWorkflowResult } from '../shared/generate-workflow';
import type { OnboardDetails } from '../shared/onboard-details';
import { moduleCopyProblems } from '$lib/modules/module-copies';
import type { Process } from '$lib/schema/workflow/process';
import { buildForm, statesNotForForms } from './build-form';
import { isDraftFormModule } from './draft-modules';
import { FORM_SYSTEM_PROMPT } from './system-prompt';

// Finds what in a drafted form must go back to the model: a state a form cannot have, and a module the model marked
// that is not one a drafted form may use or does not have the states of that module.
function draftFormProblems(process: Process) {
	return [...statesNotForForms(process), ...moduleCopyProblems(process, isDraftFormModule)];
}

/**
 * Turns a form brief into a draft workflow. The model is given the form prompt, a process with a state a form
 * cannot have or a module with the wrong states is sent back to be corrected, and the process that passes is wrapped
 * as a form.
 */
export function generateForm(details: OnboardDetails, dependencies: GenerateDependencies): Promise<GenerateWorkflowResult> {
	return generateWorkflow(
		details,
		{ subject: 'Form', system: FORM_SYSTEM_PROMPT, wrap: buildForm, checkProcess: draftFormProblems },
		dependencies
	);
}
