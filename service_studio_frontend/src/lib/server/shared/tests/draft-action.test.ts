import { describe, expect, it } from 'vitest';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { draftFromRequest } from '$lib/server/shared/draft-action';
import type { OnboardDetails } from '$lib/server/shared/onboard-details';
import { fakeModel } from '$lib/server/shared/tests/fake-model';

const dependencies = { client: fakeModel([]).client, modelId: 'the-model' };
const workflow = { manifest: {}, processes: {} } as unknown as Workflow;

// A request posted from the details page, with the fields it sends.
function posted(fields: [string, string][]): Request {
	const body = new FormData();
	for (const [name, value] of fields) body.append(name, value);
	return new Request('http://localhost/onboard/form/draft', { method: 'POST', body });
}

describe('draftFromRequest', () => {
	it('reads the name, the description and every link that was posted', async () => {
		let given: OnboardDetails | undefined;
		const request = posted([['name', 'A form'], ['description', 'What it does'], ['links', 'https://a'], ['links', '']]);
		await draftFromRequest(request, async (details) => ((given = details), { ok: true, workflow, warnings: [] }), dependencies);

		expect(given).toEqual({ name: 'A form', description: 'What it does', links: ['https://a', ''] });
	});

	it('gives the draft with the name typed, when one is made', async () => {
		const result = await draftFromRequest(posted([['name', 'A form']]), async () => ({ ok: true, workflow, warnings: ['W'] }), dependencies);
		expect(result).toEqual({ success: true, name: 'A form', workflow, warnings: ['W'] });
	});

	it('gives the problems, when no draft is made', async () => {
		const issues = [{ path: '(root)', message: 'No' }];
		const result = await draftFromRequest(posted([]), async () => ({ ok: false, issues, warnings: [] }), dependencies);
		expect(result).toEqual({ success: false, issues, warnings: [] });
	});

	it('reads missing fields as empty', async () => {
		let given: OnboardDetails | undefined;
		await draftFromRequest(posted([]), async (details) => ((given = details), { ok: true, workflow, warnings: [] }), dependencies);
		expect(given).toEqual({ name: '', description: '', links: [] });
	});
});
