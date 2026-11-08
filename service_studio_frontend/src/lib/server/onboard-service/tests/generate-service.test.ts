import type Anthropic from '@anthropic-ai/sdk';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ModelClient } from '$lib/server/shared/generate-json';
import { parseWorkflow } from '$lib/schema/workflow/validate';
import { generateService } from '../generate-service';
import { SERVICE_SYSTEM_PROMPT } from '../system-prompt';

// Stands in for the real fetch, so no test reaches the internet. Each address answers as the test says.
const fetched = vi.hoisted(() => ({ answers: {} as Record<string, { text: string } | { error: string }> }));
vi.mock('$lib/server/shared/fetch-link', () => ({
	fetchLinkText: async (url: string) => ({ url, ...(fetched.answers[url] ?? { error: 'Not set up' }) })
}));

type Request = { model: string; system: string; messages: Anthropic.MessageParam[] };

// A model that gives the next reply each time, and records every request as it was made.
function fakeModel(replies: string[]) {
	const requests: Request[] = [];
	const client: ModelClient = {
		messages: {
			stream: (params) => {
				requests.push({ model: params.model, system: params.system, messages: [...params.messages] });
				const reply = replies.shift() ?? '';
				return { finalMessage: async () => ({ content: [{ type: 'text', text: reply }] as unknown as Anthropic.ContentBlock[] }) };
			}
		}
	};
	return { client, requests };
}

// A process of the kind the prompt asks for, as the text the model would reply with.
const processReply = JSON.stringify({
	process_id: 'main',
	version: '0.1.0',
	start: 'ask',
	vars: {},
	states: {
		ask: { type: 'input', name: 'Ask', prompt: 'Your postcode?', schema: { kind: 'string' }, assign: 'postcode', next: 'look_up' },
		look_up: { type: 'call', method: 'GET', service: 'unconnected_service', url: '/unconnected', next: 'finish' },
		finish: { type: 'end', status: 'success' }
	}
});

const details = { name: 'Change my address', description: 'Change an address.', links: ['https://www.gov.uk/a', 'https://www.gov.uk/b'] };

beforeEach(() => {
	fetched.answers = { 'https://www.gov.uk/a': { text: 'Page A words' }, 'https://www.gov.uk/b': { text: 'Page B words' } };
});

describe('generateService', () => {
	it('gives a draft workflow that passes the checks, with the placeholders added', async () => {
		const { client } = fakeModel([processReply]);
		const result = await generateService(details, { client, modelId: 'the-model' });

		expect(result.ok).toBe(true);
		if (!result.ok) return;
		expect(parseWorkflow(result.workflow).ok).toBe(true);
		expect(result.workflow.manifest.id).toBe('draft.change_my_address');
		const process = result.workflow.processes.change_my_address;
		expect(process.source).toEqual(['https://www.gov.uk/a', 'https://www.gov.uk/b']);
		expect(process.states.look_up).toMatchObject({ catch: [{ on: 'any' }] });
		expect(result.warnings).toEqual([]);
	});

	it('sends the name, the description and the text of every link, with the service prompt and the model asked for', async () => {
		const { client, requests } = fakeModel([processReply]);
		await generateService(details, { client, modelId: 'the-model' });

		expect(requests[0].model).toBe('the-model');
		expect(requests[0].system).toBe(SERVICE_SYSTEM_PROMPT);
		const brief = String(requests[0].messages[0].content);
		for (const part of ['Change my address', 'Change an address.', 'Source: https://www.gov.uk/a\nPage A words', 'Page B words']) {
			expect(brief).toContain(part);
		}
	});

	it('warns about a link it could not read and still generates from the rest', async () => {
		fetched.answers['https://www.gov.uk/b'] = { error: 'Responded with status 404' };
		const { client, requests } = fakeModel([processReply]);
		const result = await generateService(details, { client, modelId: 'the-model' });

		expect(result.ok).toBe(true);
		expect(result.warnings).toEqual(['Could not read https://www.gov.uk/b: Responded with status 404']);
		expect(String(requests[0].messages[0].content)).not.toContain('Page B words');
	});

	it('asks again with the problems when the process does not pass, and uses the corrected one', async () => {
		const broken = JSON.stringify({ process_id: 'main', version: '0.1.0', start: 'ask', vars: {}, states: { ask: { type: 'end' } } });
		const { client, requests } = fakeModel([broken, processReply]);
		const result = await generateService(details, { client, modelId: 'the-model' });

		expect(result.ok).toBe(true);
		expect(requests).toHaveLength(2);
		expect(String(requests[1].messages[2].content)).toContain('states.ask.status');
	});

	it('returns the problems, and the link warnings, when the second try fails too', async () => {
		fetched.answers['https://www.gov.uk/b'] = { error: 'Timed out' };
		const { client, requests } = fakeModel(['{}', '{}']);
		const result = await generateService(details, { client, modelId: 'the-model' });

		expect(result.ok).toBe(false);
		if (result.ok) return;
		expect(result.issues.length).toBeGreaterThan(0);
		expect(result.warnings).toEqual(['Could not read https://www.gov.uk/b: Timed out']);
		expect(requests).toHaveLength(2);
	});

	it('leaves out empty links without trying to read them', async () => {
		const { client } = fakeModel([processReply]);
		const result = await generateService({ ...details, links: ['', 'https://www.gov.uk/a'] }, { client, modelId: 'the-model' });
		expect(result.warnings).toEqual([]);
	});
});
