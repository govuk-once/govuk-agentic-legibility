import { AnthropicError } from '@anthropic-ai/sdk';
import type Anthropic from '@anthropic-ai/sdk';

/*
	Asks the model for JSON, checks it, and tries once more if the check fails. The service and the form
	onboarding both need this, and the only things that differ between them are the prompt and the check, so those
	are passed in. The model client is passed in too, so the retry can be tested without calling Amazon Bedrock.
*/

// One problem found by a check: where it is and what is wrong. It is the same shape the schema checks use.
export type GenerationIssue = { path: string; message: string };

// The result of checking what the model replied: the value that was built from it, or every problem found.
export type CheckResult<T> = { ok: true; value: T } | { ok: false; issues: GenerationIssue[] };

// The part of the model client that is used. The Bedrock client fits it, and a test can supply a small fake.
export type ModelClient = {
	messages: {
		stream: (params: { model: string; max_tokens: number; system: string; messages: Anthropic.MessageParam[] }) => {
			finalMessage: () => Promise<{ content: Anthropic.ContentBlock[] }>;
		};
	};
};

export type GenerateJsonOptions<T> = {
	client: ModelClient;
	model: string;
	maxTokens: number;
	system: string;
	// The messages to start from. They are copied, so the caller's list is never changed.
	messages: Anthropic.MessageParam[];
	// Turns what the model replied into a value, or says what is wrong with it. It gets the parsed JSON.
	check: (parsed: unknown) => CheckResult<T>;
};

/**
 * Sends the messages to the model and checks the JSON in its reply. If the check fails, one more turn is
 * made that tells the model exactly which problems were found and asks it to reply again, and the result of that
 * second try is the answer. A failure of the call itself, such as a bad token or no network, is returned as a
 * problem and not thrown, because the model is an outside system and its failures are expected.
 */
export async function generateJson<T>({
	client,
	model,
	maxTokens,
	system,
	messages: startMessages,
	check
}: GenerateJsonOptions<T>): Promise<CheckResult<T>> {
	const messages = [...startMessages];

	try {
		const first = await requestJson({ client, model, maxTokens, system, messages, check });
		if (first.result.ok) return first.result;

		// One corrective turn: tell the model exactly what failed and ask it to try again.
		messages.push({ role: 'assistant', content: first.content });
		messages.push({
			role: 'user',
			content: `That did not match the required format. Problems: ${summariseIssues(first.result.issues)} Reply again with corrected JSON only.`
		});

		return (await requestJson({ client, model, maxTokens, system, messages, check })).result;
	} catch (error) {
		// A bad or expired token, a network failure or an unavailable region all throw here and never produce
		// anything to check, so they are reported in the same way as a check that failed.
		const message = error instanceof AnthropicError ? error.message : 'Could not reach Claude on Amazon Bedrock.';
		return { ok: false, issues: [{ path: '(root)', message }] };
	}
}

/**
 * Makes one request and checks the reply. The reply is also returned as the model wrote it, so it can be
 * sent back to the model if a second try is needed.
 */
async function requestJson<T>({
	client,
	model,
	maxTokens,
	system,
	messages,
	check
}: GenerateJsonOptions<T>): Promise<{ result: CheckResult<T>; content: Anthropic.ContentBlock[] }> {
	const message = await client.messages.stream({ model, max_tokens: maxTokens, system, messages }).finalMessage();
	const textBlock = message.content.find((block): block is Anthropic.TextBlock => block.type === 'text');

	let parsed: unknown;
	try {
		parsed = textBlock ? JSON.parse(textBlock.text) : undefined;
	} catch {
		parsed = undefined;
	}

	const result: CheckResult<T> =
		parsed === undefined
			? { ok: false, issues: [{ path: '(root)', message: 'The response was not valid JSON.' }] }
			: check(parsed);

	return { result, content: message.content };
}

// Writes the problems as one line, for the message that asks the model to try again.
function summariseIssues(issues: GenerationIssue[]): string {
	return issues.map((issue) => `${issue.path}: ${issue.message}`).join('; ');
}
