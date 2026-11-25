import type Anthropic from '@anthropic-ai/sdk';
import type { ModelClient } from '../generate-json';

// One request as the fake model received it.
export type FakeRequest = { model: string; system: string; messages: Anthropic.MessageParam[] };

/**
 * Makes a model for a test. It gives the next reply each time it is asked, and records every request as it was
 * made, so a test can check what was sent without calling Amazon Bedrock.
 */
export function fakeModel(replies: string[]) {
	const requests: FakeRequest[] = [];
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
