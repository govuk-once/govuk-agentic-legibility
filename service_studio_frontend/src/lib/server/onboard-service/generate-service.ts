import { generateWorkflow, type GenerateDependencies, type GenerateWorkflowResult } from '../shared/generate-workflow';
import type { OnboardDetails } from '../shared/onboard-details';
import { buildWorkflow } from './build-workflow';
import { SERVICE_SYSTEM_PROMPT } from './system-prompt';

/**
 * Turns a service brief into a draft workflow. The model is given the service prompt, and the process it writes
 * is wrapped as a service, which adds the error routes and the defaults for calls.
 */
export function generateService(details: OnboardDetails, dependencies: GenerateDependencies): Promise<GenerateWorkflowResult> {
	return generateWorkflow(details, { subject: 'Service', system: SERVICE_SYSTEM_PROMPT, wrap: buildWorkflow }, dependencies);
}
