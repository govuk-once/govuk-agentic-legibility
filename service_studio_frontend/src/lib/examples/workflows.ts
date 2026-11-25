import { parseWorkflow } from '$lib/schema/workflow/validate';
import type { WorkflowIssue } from '$lib/schema/workflow/validate';
import type { Workflow } from '$lib/schema/workflow/workflow';

/*
	How example workflows are read. Each example is a folder holding one workflow_manifest.json and one file for
	every process the manifest lists. A workflow is saved as several files, so it has to be joined back together
	before it can be checked as a whole. This file only knows how to join and check them. Each editor says which
	folder of examples is its own, so deleting one editor and its examples leaves this file working.
*/

// The file name that marks a file as the manifest. Every other file in the folder is a process.
const manifestFileName = 'workflow_manifest.json';

/**
 * Groups example files by the workflow folder they sit in: the folder name, then the file name, then the
 * parsed JSON. The keys of the modules are paths ending in the folder name and the file name. Exported so tests
 * can build a deliberately broken copy of a real example.
 */
export function groupByFolder(modules: Record<string, unknown>): Record<string, Record<string, unknown>> {
	const folders: Record<string, Record<string, unknown>> = {};
	for (const [path, content] of Object.entries(modules)) {
		const [folder, fileName] = path.split('/').slice(-2);
		(folders[folder] ??= {})[fileName] = content;
	}
	return folders;
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

/**
 * Checks every example folder as it is loaded, so one that does not match the schema still appears in the
 * list and shows its problems, rather than being left out or stopping the others loading. The list is in
 * name order.
 */
export function loadExamples(folders: Record<string, Record<string, unknown>>): WorkflowExample[] {
	return Object.entries(folders)
		.map(([slug, files]): WorkflowExample => {
			const result = parseWorkflow(assembleWorkflow(files));
			return result.ok
				? { slug, workflow: result.workflow, issues: [], warnings: result.warnings }
				: { slug, workflow: null, issues: result.issues, warnings: [] };
		})
		.sort((a, b) => a.slug.localeCompare(b.slug));
}
