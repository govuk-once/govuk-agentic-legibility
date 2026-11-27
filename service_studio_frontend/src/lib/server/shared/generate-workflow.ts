import { parseProcess, parseWorkflow } from '$lib/schema/workflow/validate';
import type { Process } from '$lib/schema/workflow/process';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { generateJson, type GenerationIssue, type ModelClient } from '$lib/server/shared/generate-json';
import type { OnboardDetails } from '$lib/server/shared/onboard-details';
import { readLinks } from '$lib/server/shared/read-links';

/*
	Turns the details a person typed into a draft workflow by asking the model for one process. A service and a
	form are drafted in the same way. What differs is the prompt, how the process is wrapped into a workflow and
	any check of its own that a kind of draft makes, so those are passed in.
*/

const MAX_TOKENS = 32000;

// What generating a draft needs from outside: the model client and the id of the model to ask. They are passed
// in, and not imported, so the generation can be tested without calling Amazon Bedrock.
export type GenerateDependencies = { client: ModelClient; modelId: string };

export type GenerateWorkflowResult = ({ ok: true; workflow: Workflow } | { ok: false; issues: GenerationIssue[] }) & {
	warnings: string[];
};

export type DraftKind = {
	// What is being drafted, in one word with a capital, such as "Service". It labels the details in the brief.
	subject: string;
	// The instructions for the model, which end with the schema the reply must match.
	system: string;
	// Wraps the process the model wrote into a whole workflow, adding what the model was not asked for.
	wrap: (process: Process, details: OnboardDetails) => Workflow;
	// A check this kind of draft makes on the process, beyond the schema. It is left out when there is none.
	checkProcess?: (process: Process) => GenerationIssue[];
};

/**
 * Asks the model for a process and returns it as a draft workflow. Every link is fetched here before the request,
 * because Bedrock has no web fetch tool for this model. The reply is checked as a process, and a failure is sent
 * back to the model once. The process that passes is then wrapped into a workflow, and the whole workflow is
 * checked again.
 *
 * Note: this should move to AWS Agent Core, with its tool calls and structured output, which would replace the
 * workarounds here for not having them.
 */
export async function generateWorkflow(
	details: OnboardDetails,
	{ subject, system, wrap, checkProcess }: DraftKind,
	{ client, modelId }: GenerateDependencies
): Promise<GenerateWorkflowResult> {
	const { sections, warnings } = await readLinks(details.links);
	const briefText = [`${subject} name: ${details.name}`, `${subject} description: ${details.description}`, ...sections].join('\n\n');

	const result = await generateJson<Workflow>({
		client,
		model: modelId,
		maxTokens: MAX_TOKENS,
		system,
		messages: [{ role: 'user', content: briefText }],
		check: (parsed) => {
			const process = parseProcess(parsed);
			if (!process.ok) return process;

			const issues = checkProcess?.(process.process) ?? [];
			if (issues.length > 0) return { ok: false, issues };

			// The whole workflow is checked too, because the wrapper adds ids and routes that the process check never saw.
			const workflow = parseWorkflow(wrap(process.process, details));
			return workflow.ok ? { ok: true, value: workflow.workflow } : workflow;
		}
	});

	return result.ok ? { ok: true, workflow: result.value, warnings } : { ok: false, issues: result.issues, warnings };
}
