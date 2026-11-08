import { fetchLinkText } from '../shared/fetch-link';
import { generateJson, type GenerationIssue, type ModelClient } from '../shared/generate-json';
import { parseProcess, parseWorkflow } from '$lib/schema/workflow/validate';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { buildWorkflow, type ServiceDetails } from './build-workflow';
import { SERVICE_SYSTEM_PROMPT } from './system-prompt';

const MAX_TOKENS = 32000;

// What generating a service needs from outside: the model client and the id of the model to ask. They are passed
// in, and not imported, so the generation can be tested without calling Amazon Bedrock.
export type GenerateServiceDependencies = { client: ModelClient; modelId: string };

export type GenerateServiceResult = ({ ok: true; workflow: Workflow } | { ok: false; issues: GenerationIssue[] }) & {
	warnings: string[];
};

/**
 * Turns a service brief into a draft workflow by asking the model for one process. Every link is fetched here
 * before the request, because Bedrock has no web fetch tool for this model. The reply is checked as a process,
 * and a failure is sent back to the model once. The process that passes is then wrapped into a workflow, which
 * adds the placeholders the model was not asked for, and the whole workflow is checked again.
 *
 * Note: this should move to AWS Agent Core, with its tool calls and structured output, which would replace the
 * workarounds here for not having them.
 */
export async function generateService(
	{ name, description, links }: ServiceDetails,
	{ client, modelId }: GenerateServiceDependencies
): Promise<GenerateServiceResult> {
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

	const briefText = [`Service name: ${name}`, `Service description: ${description}`, ...linkSections].join('\n\n');

	const result = await generateJson<Workflow>({
		client,
		model: modelId,
		maxTokens: MAX_TOKENS,
		system: SERVICE_SYSTEM_PROMPT,
		messages: [{ role: 'user', content: briefText }],
		check: (parsed) => {
			const process = parseProcess(parsed);
			if (!process.ok) return process;

			// The whole workflow is checked too, because the wrapper adds ids and routes that the process check never saw.
			const workflow = parseWorkflow(buildWorkflow(process.process, { name, description, links }));
			return workflow.ok ? { ok: true, value: workflow.workflow } : workflow;
		}
	});

	return result.ok ? { ok: true, workflow: result.value, warnings } : { ok: false, issues: result.issues, warnings };
}
