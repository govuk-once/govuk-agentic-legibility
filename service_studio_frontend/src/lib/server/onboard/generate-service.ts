import { AnthropicError } from '@anthropic-ai/sdk';
import type Anthropic from '@anthropic-ai/sdk';
import { bedrockClient, BEDROCK_MODEL_ID } from './client';
import { ONBOARD_SYSTEM_PROMPT } from './system-prompt';
import { fetchLinkText } from './fetch-link';
import { parseService } from '$lib/schema';
import type { ServiceValidation } from '$lib/schema';

const MAX_TOKENS = 32000;

export type GenerateServiceInput = { name: string; description: string; links: string[] };
export type GenerateServiceResult = ServiceValidation & { warnings: string[] };

/**
 * Turns a service brief or jounrey description into a canonical Service definition by calling Claude Sonnet 5 on
 * Amazon Bedrock. Every link is fetched here before the request, since Bedrock has no server
 * hosted web fetch tool for Claude models. Claude Sonnet 5 on Bedrock does not support
 * output_config, on either the bedrock-runtime or bedrock-mantle endpoint, so the shape comes
 * from the system prompt's own description of the format alone, then the response is validated
 * in full against parseService. One corrective turn is attempted if validation fails, whether
 * that is a shape problem or, the case this retry was originally written for, a cross
 * referential one such as a transition pointing at an id nothing defined.
 *
 *
 * Note: this method should be updated to use AWS AGEnt core and the tool calls and structured output options available via that method
 * This will provide better methods that the current proof of concept methods below which are work arounds for not using Agent Core
 */
export async function generateService({
	name,
	description,
	links
}: GenerateServiceInput): Promise<GenerateServiceResult> {
	const warnings: string[] = [];
	const fetchedLinks = await Promise.all(links.filter(Boolean).map(fetchLinkText));
	const linkSections = fetchedLinks
		.map((link) => {
			if ('error' in link) {
				warnings.push(`Could not read ${link.url}: ${link.error}`);
				return null;
			}
			return `Source: ${link.url}\n${link.text}`;
		})
		.filter((section): section is string => section !== null);

	const briefText = [
		`Service name: ${name}`,
		`Service description: ${description}`,
		...linkSections
	].join('\n\n');

	const messages: Anthropic.MessageParam[] = [{ role: 'user', content: briefText }];

	try {
		const first = await requestService(messages);
		if (first.result.ok) return { ...first.result, warnings };

		// One corrective turn: tell Claude exactly what failed validation and ask it to try again.
		messages.push({ role: 'assistant', content: first.content });
		messages.push({
			role: 'user',
			content: `That did not match the required format. Problems: ${summariseIssues(first.result)} Reply again with corrected JSON only.`
		});

		const second = await requestService(messages);
		return { ...second.result, warnings };
	} catch (error) {
		// The Bedrock call itself is an external system boundary: a bad or expired bearer token,
		// a network failure, or an unavailable region all throw here rather than producing a
		// service to validate, so they are reported the same way as a validation failure. We may want different error messaging in the future.
		const message = error instanceof AnthropicError ? error.message : 'Could not reach Claude on Amazon Bedrock.';
		return { ok: false, issues: [{ path: '(root)', message }], warnings };
	}
}

async function requestService(
	messages: Anthropic.MessageParam[]
): Promise<{ result: ServiceValidation; content: Anthropic.ContentBlock[] }> {
	const message = await bedrockClient.messages
		.stream({
			model: BEDROCK_MODEL_ID,
			max_tokens: MAX_TOKENS,
			system: ONBOARD_SYSTEM_PROMPT,
			messages
		})
		.finalMessage();

	const textBlock = message.content.find((block): block is Anthropic.TextBlock => block.type === 'text');

	let parsed: unknown;
	try {
		parsed = textBlock ? JSON.parse(textBlock.text) : undefined;
	} catch {
		parsed = undefined;
	}

	const result: ServiceValidation =
		parsed === undefined
			? { ok: false, issues: [{ path: '(root)', message: 'The response was not valid JSON.' }] }
			: parseService(parsed);

	return { result, content: message.content };
}

function summariseIssues(result: ServiceValidation): string {
	if (result.ok) return '';
	return result.issues.map((issue) => `${issue.path}: ${issue.message}`).join('; ');
}
