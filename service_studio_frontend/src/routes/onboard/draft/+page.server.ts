import type { Actions } from './$types';
import { generateService } from '$lib/server/onboard/generate-service';

export const actions: Actions = {
	default: async ({ request }) => {
		const formData = await request.formData();
		const name = String(formData.get('service-name') ?? '');
		const description = String(formData.get('service-description') ?? '');
		const links = formData.getAll('service-links').map(String);

		const result = await generateService({ name, description, links });

		if (result.ok) {
			return { success: true, service: result.service, warnings: result.warnings } as const;
		}

		return { success: false, issues: result.issues, warnings: result.warnings } as const;
	}
};
