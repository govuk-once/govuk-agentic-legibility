import type { z } from 'zod';
import { processSchema, type Process } from './process';
import { reachableInOrder } from './journey-order';
import { routesOf } from './routes';
import { workflowSchema, type Workflow } from './workflow';

/*
	Validation for the unified workflow schema. The Zod schemas check the shape of each file. The
	checks here need to look across the whole of a process, for example whether a next state really
	exists, which a single state schema cannot see.

	Problems come in two kinds. An issue is an error that stops the workflow being saved or sent. A
	warning is something worth a look that does not stop it, for example a state that nothing leads
	to. Warnings are only worked out when there are no errors, because they read routes that an
	error may have left pointing nowhere.
*/

// One problem found, flattened to a dotted path and a message so it can be listed directly in a
// GOV.UK error summary. Errors and warnings share this shape.
export type WorkflowIssue = { path: string; message: string };

export type ProcessValidation =
	| { ok: true; process: Process; warnings: WorkflowIssue[] }
	| { ok: false; issues: WorkflowIssue[] };

export type WorkflowValidation =
	| { ok: true; workflow: Workflow; warnings: WorkflowIssue[] }
	| { ok: false; issues: WorkflowIssue[] };

/**
 * Turns the issues from a failed Zod parse into the flat path and message shape used everywhere
 * else, so callers never have to read Zod's own error format. A problem at the very top of the
 * input has an empty path, which is shown as "(root)".
 */
function issuesFromZod(error: z.ZodError): WorkflowIssue[] {
	return error.issues.map((issue) => ({
		path: issue.path.length ? issue.path.join('.') : '(root)',
		message: issue.message
	}));
}

/**
 * Checks that the states of one process hang together: the start state exists, every state it
 * points at exists, and the process has an end. The path prefix lets the same checks run on a
 * process inside a workflow, where the path needs to begin with the process name.
 *
 * A state with no way on is not checked here. The schema already requires every state except an
 * end state to name where it goes next, or to have a default, so it cannot be missing.
 */
function checkProcess(process: Process, pathPrefix = ''): WorkflowIssue[] {
	const issues: WorkflowIssue[] = [];
	const hasState = (name: string) => name in process.states;

	if (!hasState(process.start)) {
		issues.push({
			path: `${pathPrefix}start`,
			message: `The start state "${process.start}" does not exist in this process`
		});
	}

	// Every route out of every state must lead to a state that exists in the same process.
	for (const [name, state] of Object.entries(process.states)) {
		for (const route of routesOf(state)) {
			if (!hasState(route.target)) {
				issues.push({
					path: `${pathPrefix}states.${name}.${route.path.join('.')}`,
					message: `Points to "${route.target}", but this process has no state with that name`
				});
			}
		}
	}

	if (!Object.values(process.states).some((state) => state.type === 'end')) {
		issues.push({ path: `${pathPrefix}states`, message: 'A process needs at least one end state' });
	}

	return issues;
}

/**
 * Checks that the manifest and its process files agree with each other: the entry process is
 * listed, every listed process has a file at the listed version, no file is left unlisted, and every
 * invoke state runs a process that exists. Each process is also given the checks that apply inside
 * one process, with its path starting from the process name.
 */
function checkWorkflow(workflow: Workflow): WorkflowIssue[] {
	const { manifest, processes } = workflow;
	const issues: WorkflowIssue[] = [];
	const listedIds = manifest.processes.map((listed) => listed.process_id);

	if (!listedIds.includes(manifest.entry)) {
		issues.push({
			path: 'manifest.entry',
			message: `The entry process "${manifest.entry}" is not in the list of processes`
		});
	}

	manifest.processes.forEach((listed, index) => {
		// The same process listed twice would make the version and the file ambiguous.
		if (listedIds.indexOf(listed.process_id) !== index) {
			issues.push({
				path: `manifest.processes.${index}.process_id`,
				message: `"${listed.process_id}" is listed more than once`
			});
		}

		const file = processes[listed.process_id];
		if (!file) {
			issues.push({
				path: `manifest.processes.${index}`,
				message: `No process file was found for "${listed.process_id}"`
			});
		} else if (file.version !== listed.version) {
			issues.push({
				path: `processes.${listed.process_id}.version`,
				message: `The version is "${file.version}" but the manifest lists "${listed.version}"`
			});
		}
	});

	for (const [key, process] of Object.entries(processes)) {
		// Processes are looked up by key, so the key and the id inside the file must be the same.
		if (process.process_id !== key) {
			issues.push({
				path: `processes.${key}.process_id`,
				message: `The process_id "${process.process_id}" does not match its key "${key}"`
			});
		}

		if (!listedIds.includes(key)) {
			issues.push({ path: `processes.${key}`, message: `"${key}" is not listed in the manifest` });
		}

		issues.push(...checkProcess(process, `processes.${key}.`));

		for (const [name, state] of Object.entries(process.states)) {
			if (state.type === 'invoke' && !(state.process in processes)) {
				issues.push({
					path: `processes.${key}.states.${name}.process`,
					message: `Runs "${state.process}", but the workflow has no process with that name`
				});
			}
		}
	}

	return issues;
}

/**
 * Warns about each state in a process that no route leads to. Such a state is harmless but can
 * never run, which usually means a route was removed by mistake or a step was left behind.
 */
function warnAboutProcess(process: Process, pathPrefix = ''): WorkflowIssue[] {
	const reached = new Set(reachableInOrder(process));

	return Object.keys(process.states)
		.filter((name) => !reached.has(name))
		.map((name) => ({
			path: `${pathPrefix}states.${name}`,
			message: 'No route leads to this state, so it can never run'
		}));
}

/**
 * Warns about the parts of a workflow that hang together but do nothing useful: states that nothing
 * leads to, processes that no state runs, and invoke catch names that match no end outcome of the
 * process being run. A process counts as run when a reachable state in a run process invokes it,
 * starting from the entry process.
 */
function warnAboutWorkflow(workflow: Workflow): WorkflowIssue[] {
	const { manifest, processes } = workflow;
	const warnings: WorkflowIssue[] = [];

	for (const [key, process] of Object.entries(processes)) {
		warnings.push(...warnAboutProcess(process, `processes.${key}.`));

		for (const [name, state] of Object.entries(process.states)) {
			if (state.type !== 'invoke') continue;

			// The names an invoke can catch are the outcomes of the end states of the process it runs.
			// The name "any" catches everything, so it is never checked.
			const outcomes = new Set(
				Object.values(processes[state.process].states).flatMap((end) => (end.type === 'end' && end.outcome ? [end.outcome] : []))
			);
			(state.catch ?? []).forEach((clause, index) => {
				if (clause.on !== 'any' && !outcomes.has(clause.on)) {
					warnings.push({
						path: `processes.${key}.states.${name}.catch.${index}.on`,
						message: `"${clause.on}" is not the outcome of any end state in "${state.process}"`
					});
				}
			});
		}
	}

	// Follow invoke states from the entry process to find every process that can run.
	const used = new Set<string>();
	const waiting = [manifest.entry];
	while (waiting.length) {
		const id = waiting.pop()!;
		if (used.has(id)) continue;
		used.add(id);

		const process = processes[id];
		for (const name of reachableInOrder(process)) {
			const state = process.states[name];
			if (state.type === 'invoke') waiting.push(state.process);
		}
	}

	for (const id of Object.keys(processes)) {
		if (!used.has(id)) {
			warnings.push({ path: `processes.${id}`, message: 'No state runs this process, so it can never run' });
		}
	}

	return warnings;
}

/**
 * Validates one process file. The shape is checked first. The checks across its states only run
 * once the shape is sound, because they read keys that a malformed state may not have. Returns the
 * typed process on success, or a flat list of path and message issues on failure.
 */
export function parseProcess(input: unknown): ProcessValidation {
	const result = processSchema.safeParse(input);
	if (!result.success) return { ok: false, issues: issuesFromZod(result.error) };

	const issues = checkProcess(result.data);
	if (issues.length) return { ok: false, issues };

	return { ok: true, process: result.data, warnings: warnAboutProcess(result.data) };
}

/**
 * Validates a manifest and its process files as one assembled workflow. The shape of every file is
 * checked first, and the checks across files only run once the shape is sound. Returns the typed
 * workflow on success, or a flat list of path and message issues on failure.
 */
export function parseWorkflow(input: unknown): WorkflowValidation {
	const result = workflowSchema.safeParse(input);
	if (!result.success) return { ok: false, issues: issuesFromZod(result.error) };

	const issues = checkWorkflow(result.data);
	if (issues.length) return { ok: false, issues };

	return { ok: true, workflow: result.data, warnings: warnAboutWorkflow(result.data) };
}
