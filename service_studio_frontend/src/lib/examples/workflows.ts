import { parseWorkflow } from '$lib/schema/workflow/validate';
import type { WorkflowIssue } from '$lib/schema/workflow/validate';
import type { Workflow } from '$lib/schema/workflow/workflow';

/*
	The example workflows, each a folder holding one workflow_manifest.json and one file for every
	process the manifest lists. A workflow is saved as several files, so it has to be joined back
	together before it can be checked as a whole.
*/

// The file name that marks a file as the manifest. Every other file in the folder is a process.
const manifestFileName = 'workflow_manifest.json';

// import.meta.glob eagerly bundles every example file at build time, so the list of examples needs no
// server round trip. The pattern only reaches one folder down, which is one folder per workflow.
const modules = import.meta.glob('./new-examples/*/*.json', { eager: true, import: 'default' });

/**
 * Every example file grouped by its workflow folder: the folder name, then the file name, then the
 * parsed JSON. Exported so tests can build a deliberately broken copy of a real example.
 */
export const exampleFolders: Record<string, Record<string, unknown>> = {};
for (const [path, content] of Object.entries(modules)) {
	const [folder, fileName] = path.split('/').slice(-2);
	(exampleFolders[folder] ??= {})[fileName] = content;
}

/**
 * Joins the files of one workflow folder into the single object that parseWorkflow checks. The
 * manifest is picked out by its file name, and every other file becomes a process keyed by its file
 * name without the .json ending. Keying by file name means a file saved under the wrong name is
 * caught by the key and process_id check, rather than hidden.
 */
export function assembleWorkflow(files: Record<string, unknown>): {
	manifest: unknown;
	processes: Record<string, unknown>;
} {
	const processes: Record<string, unknown> = {};

	for (const [fileName, content] of Object.entries(files)) {
		if (fileName !== manifestFileName) processes[fileName.replace(/\.json$/, '')] = content;
	}

	return { manifest: files[manifestFileName], processes };
}

export type WorkflowExample = {
	slug: string;
	workflow: Workflow | null;
	issues: WorkflowIssue[];
	warnings: WorkflowIssue[];
};

// Each example is checked as it is loaded, so one that does not match the schema still appears in the
// list and shows its problems, rather than being left out or stopping the others loading.
export const workflowExamples: WorkflowExample[] = Object.entries(exampleFolders)
	.map(([slug, files]) => {
		const result = parseWorkflow(assembleWorkflow(files));
		return result.ok
			? { slug, workflow: result.workflow, issues: [], warnings: result.warnings }
			: { slug, workflow: null, issues: result.issues, warnings: [] };
	})
	.sort((a, b) => a.slug.localeCompare(b.slug));
