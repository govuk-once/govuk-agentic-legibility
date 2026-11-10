import type { Actions } from './$types';
import { generateService } from '$lib/server/onboard-service/generate-service';
import { bedrockClient, BEDROCK_MODEL_ID } from '$lib/server/shared/client';

export const actions: Actions = {
	default: async ({ request }) => {
		const formData = await request.formData();
		const name = String(formData.get('name') ?? '');
		const description = String(formData.get('description') ?? '');
		const links = formData.getAll('links').map(String);

		// The client and the model are handed in here, on the server, so the generation itself never imports the token.
		const result = await generateService({ name, description, links }, { client: bedrockClient, modelId: BEDROCK_MODEL_ID });

		if (result.ok) {
			return { success: true, name, workflow: result.workflow, warnings: result.warnings } as const;
		}

		return { success: false, issues: result.issues, warnings: result.warnings } as const;
	}
};
