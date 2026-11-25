import { generateWorkflow, type GenerateDependencies, type GenerateWorkflowResult } from '../shared/generate-workflow';
import type { OnboardDetails } from '../shared/onboard-details';
import { buildForm, statesNotForForms } from './build-form';
import { FORM_SYSTEM_PROMPT } from './system-prompt';

/**
 * Turns a form brief into a draft workflow. The model is given the form prompt, a process with a state a form
 * cannot have is sent back to be corrected, and the process that passes is wrapped as a form.
 */
export function generateForm(details: OnboardDetails, dependencies: GenerateDependencies): Promise<GenerateWorkflowResult> {
	return generateWorkflow(
		details,
		{ subject: 'Form', system: FORM_SYSTEM_PROMPT, wrap: buildForm, checkProcess: statesNotForForms },
		dependencies
	);
}
