import { AnthropicError } from '@anthropic-ai/sdk';
import type Anthropic from '@anthropic-ai/sdk';
import type { AnthropicBedrock } from '@anthropic-ai/bedrock-sdk';
import { describe, expect, it } from 'vitest';
import { generateJson, type CheckResult, type ModelClient } from '../generate-json';

// Fails to compile if the real Bedrock client no longer fits the small client type that the helper asks for.
export const bedrockFits = (client: AnthropicBedrock): ModelClient => client;

type Request = { model: string; max_tokens: number; system: string; messages: Anthropic.MessageParam[] };

// A model that gives the next reply from the list each time it is asked, or throws it if it is an error. Every
// request is recorded as it was when it was made.
function fakeModel(replies: (string | Error)[]) {
	const requests: Request[] = [];
	const client: ModelClient = {
		messages: {
			stream: (params) => {
				requests.push({ ...params, messages: [...params.messages] });
				const reply = replies.shift();
				return {
					finalMessage: async () => {
						if (reply instanceof Error) throw reply;
						return { content: [{ type: 'text', text: reply ?? '' }] as unknown as Anthropic.ContentBlock[] };
					}
				};
			}
		}
	};
	return { client, requests };
}

// A check that wants an object with a name, and says what is missing otherwise.
const needsName = (parsed: unknown): CheckResult<string> => {
	const name = (parsed as { name?: unknown }).name;
	return typeof name === 'string' ? { ok: true, value: name } : { ok: false, issues: [{ path: 'name', message: 'Required' }] };
};

const options = (client: ModelClient) => ({
	client,
	model: 'a-model',
	maxTokens: 100,
	system: 'Be brief',
	messages: [{ role: 'user', content: 'Make one' }] as Anthropic.MessageParam[],
	check: needsName
});

describe('generateJson', () => {
	it('gives the value when the first reply passes the check, with one request', async () => {
		const { client, requests } = fakeModel(['{"name": "Ada"}']);
		expect(await generateJson(options(client))).toEqual({ ok: true, value: 'Ada' });
		expect(requests).toHaveLength(1);
		expect(requests[0]).toMatchObject({ model: 'a-model', max_tokens: 100, system: 'Be brief' });
	});

	it('tells the model what was wrong and uses the second reply when it passes', async () => {
		const { client, requests } = fakeModel(['{"other": 1}', '{"name": "Ada"}']);
		expect(await generateJson(options(client))).toEqual({ ok: true, value: 'Ada' });

		expect(requests).toHaveLength(2);
		const second = requests[1].messages;
		expect(second).toHaveLength(3);
		expect(second[1]).toMatchObject({ role: 'assistant' });
		expect(second[2]).toMatchObject({ role: 'user' });
		expect(second[2].content).toContain('name: Required');
		expect(second[2].content).toContain('Reply again with corrected JSON only.');
	});

	it('does not try a third time when the second reply fails too', async () => {
		const { client, requests } = fakeModel(['{}', '{}', '{"name": "Never asked"}']);
		expect(await generateJson(options(client))).toEqual({ ok: false, issues: [{ path: 'name', message: 'Required' }] });
		expect(requests).toHaveLength(2);
	});

	it('counts a reply that is not JSON as a failed check and asks again', async () => {
		const { client, requests } = fakeModel(['Sorry, here you go: {', '{"name": "Ada"}']);
		expect(await generateJson(options(client))).toEqual({ ok: true, value: 'Ada' });
		expect(requests[1].messages[2].content).toContain('The response was not valid JSON.');
	});

	it('returns the failure of the call itself as a problem, using the message the error carries', async () => {
		const { client, requests } = fakeModel([new AnthropicError('Token expired')]);
		expect(await generateJson(options(client))).toEqual({ ok: false, issues: [{ path: '(root)', message: 'Token expired' }] });
		expect(requests).toHaveLength(1);
	});

	it('gives a plain message for any other failure, so no internal detail is shown', async () => {
		const { client } = fakeModel([new Error('socket hang up at 10.0.0.1')]);
		const result = await generateJson(options(client));
		expect(result).toEqual({ ok: false, issues: [{ path: '(root)', message: 'Could not reach Claude on Amazon Bedrock.' }] });
	});

	it('does not change the messages it was given', async () => {
		const { client } = fakeModel(['{}', '{}']);
		const given = options(client);
		await generateJson(given);
		expect(given.messages).toHaveLength(1);
	});
});
