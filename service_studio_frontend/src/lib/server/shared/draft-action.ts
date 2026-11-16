import type { GenerateDependencies, GenerateWorkflowResult } from './generate-workflow';
import type { OnboardDetails } from './onboard-details';

// Turns the details a person typed into a draft. A service and a form each have one of these.
type Generate = (details: OnboardDetails, dependencies: GenerateDependencies) => Promise<GenerateWorkflowResult>;

/**
 * Does the work of the form action on a draft page: reads the details that were posted, asks for the draft and
 * returns what the page shows. The fields are the ones the details page posts, which are name, description and
 * links. A service and a form post the same details, so both draft pages use this.
 */
export async function draftFromRequest(request: Request, generate: Generate, dependencies: GenerateDependencies) {
	const formData = await request.formData();
	const details: OnboardDetails = {
		name: String(formData.get('name') ?? ''),
		description: String(formData.get('description') ?? ''),
		links: formData.getAll('links').map(String)
	};

	const result = await generate(details, dependencies);

	if (result.ok) {
		return { success: true, name: details.name, workflow: result.workflow, warnings: result.warnings } as const;
	}
	return { success: false, issues: result.issues, warnings: result.warnings } as const;
}
