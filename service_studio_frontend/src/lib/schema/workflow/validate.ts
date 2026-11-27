import type { z } from 'zod';
import { hasNext } from '$lib/schema/frontend/edit-state';
import { isUndecidedRule, placeholderMessage, placeholderQuestion } from '$lib/schema/frontend/placeholders';
import { processSchema, type Process } from '$lib/schema/workflow/process';
import { journeyOrder, reachableInOrder } from '$lib/schema/frontend/journey-order';
import { schemaProblemTitle, wordsFor, type JourneyProblemKind } from '$lib/schema/frontend/journey-problems';
import { routesOf } from '$lib/schema/frontend/routes';
import type { WorkingProcess, WorkingWorkflow } from '$lib/schema/frontend/working-process';
import { workflowSchema, type Workflow } from '$lib/schema/workflow/workflow';

/*
	Validation for the unified workflow schema. The Zod schemas check the shape of each file. The
	checks here need to look across the whole of a process, for example whether a next state really
	exists, which a single state schema cannot see.

	There may be two kinds of problem. An issue is an error that stops the workflow being saved or sent. A
	warning is something worth a look that does not stop it, for example a state that nothing leads
	to. Warnings are only worked out when there are no errors, because they read routes that an
	error may have left pointing nowhere.

	The editor allows some things that a saved workflow does not, such as a step with nothing after it, while
	a journey is being built. journeyErrors and checkBeforeProceeding are where those are reported, together with
	everything else, and journeyWarnings lists what is worth finishing but does not stop a journey.
*/

// A problem found, flattened to a dotted path and a message so it can be listed directly in a
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
 * Checks that the states of one process stay together: the start state exists, every state it
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

	if (!Object.values(process.states).some((state) => state.state_type === 'end')) {
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
			if (state.state_type === 'invoke' && !(state.process in processes)) {
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
 * Lists the states of a process that cannot be reached from its start by any route, error routes included.
 */
function unreachableStates(process: WorkingProcess): string[] {
	const reached = new Set(reachableInOrder(process));
	return Object.keys(process.states).filter((name) => !reached.has(name));
}

/**
 * Warns about each state in a process that no route leads to. Such a state is harmless but can
 * never run, which usually means a route was removed by mistake or a step was left behind.
 */
function warnAboutProcess(process: Process, pathPrefix = ''): WorkflowIssue[] {
	return unreachableStates(process).map((name) => ({
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
			if (state.state_type !== 'invoke') continue;

			// The names an invoke can catch are the outcomes of the end states of the process it runs.
			// The name "any" catches everything, so it is never checked.
			const outcomes = new Set(
				Object.values(processes[state.process].states).flatMap((end) => (end.state_type === 'end' && end.outcome ? [end.outcome] : []))
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
			if (state.state_type === 'invoke') waiting.push(state.process);
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
 * once the shape is ok, because they read keys that a malformed state may not have. Returns the
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
 * checked first, and the checks across files only run once the shape is ok. Returns the typed
 * workflow on success, or a flat list of path and message issues on failure.
 */
export function parseWorkflow(input: unknown): WorkflowValidation {
	const result = workflowSchema.safeParse(input);
	if (!result.success) return { ok: false, issues: issuesFromZod(result.error) };

	const issues = checkWorkflow(result.data);
	if (issues.length) return { ok: false, issues };

	return { ok: true, workflow: result.data, warnings: warnAboutWorkflow(result.data) };
}

/**
 * One problem with a journey that is being edited: where it is in the process, the state it is about when it is
 * about one, its sort, and its words from journey-problems.ts.
 */
export type JourneyProblem = { path: string; state?: string; kind: JourneyProblemKind; message: string; title: string; fix: string; howToFix?: string };

/**
 * Finds the first state of each piece of the journey that is not joined to the start. Every state cut off behind
 * one of them is left out, because joining the first state joins them too, so one cause gives one problem. A piece
 * that is a loop, with nothing outside leading into it, is named by its first state in journey order.
 */
function firstStatesOfLoosePieces(process: WorkingProcess): string[] {
	const reached = new Set(reachableInOrder(process));
	const loose = journeyOrder(process).filter((code) => !reached.has(code));
	const ledTo = new Set(loose.flatMap((code) => routesOf(process.states[code]).map((route) => route.target)));

	// States that nothing leads to come first, then any loop that is left, so each piece is named once.
	const covered = new Set<string>();
	const firsts: string[] = [];
	for (const code of [...loose.filter((each) => !ledTo.has(each)), ...loose]) {
		if (covered.has(code)) continue;
		firsts.push(code);
		for (const each of reachableInOrder({ ...process, start: code })) covered.add(each);
	}
	return firsts;
}

/**
 * Lists what stops a journey that is being edited from being passed on: a missing start, a step with nothing after
 * it, a decision with a way out that leads nowhere, a piece that is not joined to the start, and anything the schema
 * finds. A missing key that the schema also reports is only listed once, in these words.
 */
export function journeyErrors(process: WorkingProcess): JourneyProblem[] {
	return findJourneyErrors(process).problems;
}

/**
 * Does the work of journeyErrors, and also gives every path the problems cover. A decision is one problem however
 * many of its ways out are missing, so it covers more paths than the one it names, and the schema's own words for
 * each of them are left out.
 */
function findJourneyErrors(process: WorkingProcess): { problems: JourneyProblem[]; covered: Set<string> } {
	const problems: JourneyProblem[] = [];
	const covered = new Set<string>();
	if (process.start === undefined) problems.push({ path: 'start', ...wordsFor('no_start') });

	for (const [code, state] of Object.entries(process.states)) {
		if (hasNext(state) && state.next === undefined) {
			problems.push({ path: `states.${code}.next`, state: code, ...wordsFor('no_next') });
		}

		// A decision is listed once however many of its ways out lead nowhere, with the path of the first.
		if (state.state_type === 'choice') {
			const missing = [
				...state.rules.flatMap((rule, index) => (rule.next === undefined ? [`states.${code}.rules.${index}.next`] : [])),
				...(state.default === undefined ? [`states.${code}.default`] : [])
			];
			for (const path of missing) covered.add(path);
			if (missing.length > 0) {
				problems.push({ path: missing[0], state: code, ...wordsFor('way_out_leads_nowhere', missing.length) });
			}
		}
	}

	for (const code of firstStatesOfLoosePieces(process)) {
		problems.push({ path: `states.${code}`, state: code, ...wordsFor('not_joined') });
	}

	// The schema words a missing key in its own way, so a key already listed is left out and not said twice.
	for (const problem of problems) covered.add(problem.path);
	const parsed = parseProcess(process);
	const fromSchema = parsed.ok ? [] : parsed.issues.filter((issue) => !listedUnder(covered, issue.path));
	// The schema's own words say what is wrong, so they are the fix under a title that says where they come from.
	const schemaProblems = fromSchema.map((issue): JourneyProblem => ({ ...issue, state: stateOfPath(issue.path), kind: 'schema', title: schemaProblemTitle, fix: issue.message }));
	return { problems: [...problems, ...schemaProblems], covered };
}

/**
 * Lists what is worth finishing before a journey is passed on but does not stop it: placeholder words left in a
 * question or a message, and decision rules that are still to be confirmed. Placeholders that a later review fills
 * in, such as the owner or the details of a call, are not listed, because the person editing does not set them.
 */
export function journeyWarnings(process: WorkingProcess): JourneyProblem[] {
	return Object.entries(process.states).flatMap(([code, state]): JourneyProblem[] => {
		if (state.state_type === 'input' && state.prompt === placeholderQuestion) {
			return [{ path: `states.${code}.prompt`, state: code, ...wordsFor('placeholder_question') }];
		}
		if (state.state_type === 'output' && state.message === placeholderMessage) {
			return [{ path: `states.${code}.message`, state: code, ...wordsFor('placeholder_message') }];
		}
		if (state.state_type === 'choice') {
			const undecided = state.rules.filter((rule) => isUndecidedRule(rule.when)).length;
			if (undecided === 0) return [];
			return [{ path: `states.${code}.rules`, state: code, ...wordsFor('rule_to_confirm', undecided) }];
		}
		return [];
	});
}

// Tells whether a path from the schema is one already listed, or sits inside one, such as a rule of a decision
// whose way out is already reported.
function listedUnder(listed: Set<string>, path: string): boolean {
	return [...listed].some((each) => path === each || path.startsWith(`${each}.`));
}

// Reads the state a path from the schema is about, such as step_1 from "states.step_1.prompt", or nothing when it is
// about the process as a whole.
function stateOfPath(path: string): string | undefined {
	const parts = path.split('.');
	return parts[0] === 'states' ? parts[1] : undefined;
}

/**
 * Checks a workflow that is being edited, to decide whether it can be passed on for review. Each process is checked
 * with journeyErrors, and then the workflow as a whole, for anything across its files, so the whole list can be
 * shown at once. An empty list means the
 * journey is ready. Warnings, such as a process that nothing runs, do not stop a journey being passed on, so they
 * are not included.
 */
export function checkBeforeProceeding(workflow: WorkingWorkflow): WorkflowIssue[] {
	const listed = new Set<string>();
	const fromProcesses = Object.entries(workflow.processes).flatMap(([key, process]) => {
		const { problems, covered } = findJourneyErrors(process);
		for (const path of covered) listed.add(`processes.${key}.${path}`);
		return problems.map((problem) => ({
			path: `processes.${key}.${problem.path}`,
			message: problem.state ? `${problem.state} ${problem.message}` : problem.message
		}));
	});

	// The workflow is checked as a whole as well, for anything across its files. What it says again about a key that
	// is already listed is left out, so nothing is said twice.
	for (const issue of fromProcesses) listed.add(issue.path);
	const result = parseWorkflow(workflow);
	return [...fromProcesses, ...(result.ok ? [] : result.issues.filter((issue) => !listedUnder(listed, issue.path)))];
}
