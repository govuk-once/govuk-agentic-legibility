import { describe, expect, it } from 'vitest';
import { exampleProcessFiles, exampleWorkflows } from '$lib/schema/workflow/tests/example-states';
import { formExamples } from '$lib/examples/forms';
import {
	placeholderInput,
	placeholderMessage,
	placeholderOutput,
	placeholderQuestion,
	unconnectedApiCallDetails,
	undecidedRule
} from '$lib/schema/workflow/placeholders';
import { checkBeforeProceeding, journeyErrors, journeyWarnings, parseProcess, parseWorkflow } from '$lib/schema/workflow/validate';
import type { WorkingProcess, WorkingWorkflow } from '$lib/schema/workflow/working-process';

// A small valid process that each test copies and then breaks in one way.
const process = {
	process_id: 'check_attendance',
	version: '0.1.0',
	start: 'ask',
	vars: { attended: null },
	states: {
		ask: {
			state_type: 'input',
			prompt: 'Did you attend?',
			schema: { kind: 'boolean' },
			assign: 'attended',
			next: 'branch'
		},
		branch: {
			state_type: 'choice',
			rules: [{ when: { op: 'is_true', path: 'attended' }, next: 'finish' }],
			default: 'ask'
		},
		finish: { state_type: 'end', status: 'success' }
	}
};

describe('parseProcess with the real examples', () => {
	it('accepts every process file in the example services', () => {
		for (const file of exampleProcessFiles()) {
			const result = parseProcess(file);
			expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
		}
	});
});

describe('parseProcess', () => {
	it('returns the typed process when it is valid', () => {
		const result = parseProcess(process);
		expect(result.ok).toBe(true);
		if (result.ok) expect(result.process.process_id).toBe('check_attendance');
	});

	it('reports a shape problem with a dotted path', () => {
		const broken = { ...process, states: { ...process.states, finish: { state_type: 'end' } } };
		const result = parseProcess(broken);
		expect(result).toMatchObject({ ok: false });
		if (!result.ok) expect(result.issues.map((issue) => issue.path)).toContain('states.finish.status');
	});

	it('reports a problem at the very top of the input as the root', () => {
		const result = parseProcess('not a process');
		expect(result).toMatchObject({ ok: false, issues: [{ path: '(root)' }] });
	});

	it('reports a start state that does not exist', () => {
		const result = parseProcess({ ...process, start: 'missing' });
		expect(result).toMatchObject({ ok: false, issues: [{ path: 'start' }] });
	});

	it('reports a next state that does not exist', () => {
		const states = { ...process.states, ask: { ...process.states.ask, next: 'nowhere' } };
		const result = parseProcess({ ...process, states });
		expect(result).toMatchObject({ ok: false, issues: [{ path: 'states.ask.next', message: expect.stringContaining('nowhere') }] });
	});

	it('reports a missing target inside a choice rule, the default and a timeout', () => {
		const states = {
			...process.states,
			ask: { ...process.states.ask, timeout: { after: 'PT5S', next: 'gone_timeout' } },
			branch: {
				state_type: 'choice',
				rules: [{ when: { op: 'is_true', path: 'attended' }, next: 'gone_rule' }],
				default: 'gone_default'
			}
		};
		const result = parseProcess({ ...process, states });
		const paths = !result.ok ? result.issues.map((issue) => issue.path) : [];
		expect(paths).toEqual(['states.ask.timeout.next', 'states.branch.rules.0.next', 'states.branch.default']);
	});

	it('reports a missing target inside a catch clause', () => {
		const call = { state_type: 'api_call', method: 'GET', service: 'dwp', url: '/x', catch: [{ on: 'any', next: 'gone' }], next: 'finish' };
		const result = parseProcess({ ...process, start: 'fetch', states: { fetch: call, finish: process.states.finish } });
		expect(result).toMatchObject({ ok: false, issues: [{ path: 'states.fetch.catch.0.next' }] });
	});

	it('reports a process with no end state', () => {
		const states = { ask: { ...process.states.ask, next: 'ask' } };
		const result = parseProcess({ ...process, states });
		expect(result).toMatchObject({ ok: false, issues: [{ path: 'states', message: 'A process needs at least one end state' }] });
	});

	it('reports every problem at once', () => {
		const states = { ask: { ...process.states.ask, next: 'nowhere' } };
		const result = parseProcess({ ...process, start: 'missing', states });
		expect(!result.ok && result.issues.length).toBe(3);
	});

	it('does not run the cross state checks when the shape is wrong', () => {
		const result = parseProcess({ ...process, states: { ask: { state_type: 'input' } } });
		expect(result.ok).toBe(false);
	});
});

// A small valid workflow of two processes: the entry process runs a section and carries on.
const manifest = {
	workflow_id: 1,
	schema: 'Workflow/0.2',
	id: 'dwp.attendance',
	version: '0.1.0',
	owner: 'DWP',
	contact: 'owner@example.gov.uk',
	description: 'Checks attendance.',
	state: 'draft',
	entry: 'main',
	executor: {
		workflow_id_template: 'attendance-{{input.id}}',
		id_reuse_policy: 'reject_duplicate',
		run_timeout: 'P14D',
		search_attributes: {}
	},
	defaults: {},
	processes: [
		{ process_id: 'main', version: '0.1.0' },
		{ process_id: 'section', version: '0.1.0' }
	]
};

const finish = { state_type: 'end', status: 'success' };

const workflow = {
	manifest,
	processes: {
		main: {
			process_id: 'main',
			version: '0.1.0',
			start: 'run_section',
			vars: {},
			states: { run_section: { state_type: 'invoke', process: 'section', next: 'finish' }, finish }
		},
		section: {
			process_id: 'section',
			version: '0.1.0',
			start: 'finish',
			vars: {},
			states: { finish }
		}
	}
};

// Returns the paths of the issues, or an empty list when the workflow is valid.
function issuePaths(input: unknown): string[] {
	const result = parseWorkflow(input);
	return result.ok ? [] : result.issues.map((issue) => issue.path);
}

describe('parseWorkflow with the real examples', () => {
	it.each(['change_of_address', 'maternity_allowance'])('accepts the %s workflow', (name) => {
		const example = exampleWorkflows().find((candidate) => candidate.name === name);
		const result = parseWorkflow({ manifest: example?.manifest, processes: example?.processes });
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
	});
});

describe('parseWorkflow', () => {
	it('returns the typed workflow when it is valid', () => {
		const result = parseWorkflow(workflow);
		expect(result.ok).toBe(true);
		if (result.ok) expect(Object.keys(result.workflow.processes)).toEqual(['main', 'section']);
	});

	it('reports a shape problem in a process with the process name in the path', () => {
		const broken = { ...workflow, processes: { ...workflow.processes, section: { ...workflow.processes.section, version: '1' } } };
		expect(issuePaths(broken)).toEqual(['processes.section.version']);
	});

	it('reports a problem inside one process with the process name in the path', () => {
		const states = { run_section: { state_type: 'invoke', process: 'section', next: 'nowhere' }, finish };
		const broken = { ...workflow, processes: { ...workflow.processes, main: { ...workflow.processes.main, states } } };
		expect(issuePaths(broken)).toEqual(['processes.main.states.run_section.next']);
	});

	it('reports an entry process that is not listed', () => {
		const broken = { ...workflow, manifest: { ...manifest, entry: 'other' } };
		expect(issuePaths(broken)).toEqual(['manifest.entry']);
	});

	it('reports a listed process that has no file', () => {
		const { section: _removed, ...processes } = workflow.processes;
		const result = parseWorkflow({ ...workflow, processes });
		expect(!result.ok && result.issues.map((issue) => issue.path)).toContain('manifest.processes.1');
	});

	it('reports a process file whose version differs from the manifest', () => {
		const section = { ...workflow.processes.section, version: '0.2.0' };
		const broken = { ...workflow, processes: { ...workflow.processes, section } };
		expect(issuePaths(broken)).toEqual(['processes.section.version']);
	});

	it('reports a process whose id does not match its key', () => {
		const section = { ...workflow.processes.section, process_id: 'renamed' };
		const broken = { ...workflow, processes: { ...workflow.processes, section } };
		expect(issuePaths(broken)).toEqual(['processes.section.process_id']);
	});

	it('reports a process file that the manifest does not list', () => {
		const extra = { ...workflow.processes.section, process_id: 'extra' };
		const broken = { ...workflow, processes: { ...workflow.processes, extra } };
		expect(issuePaths(broken)).toEqual(['processes.extra']);
	});

	it('reports a process that is listed twice', () => {
		const processes = [...manifest.processes, { process_id: 'section', version: '0.1.0' }];
		const broken = { ...workflow, manifest: { ...manifest, processes } };
		expect(issuePaths(broken)).toEqual(['manifest.processes.2.process_id']);
	});

	it('reports an invoke state that runs a process that does not exist', () => {
		const states = { run_section: { state_type: 'invoke', process: 'missing', next: 'finish' }, finish };
		const broken = { ...workflow, processes: { ...workflow.processes, main: { ...workflow.processes.main, states } } };
		expect(issuePaths(broken)).toEqual(['processes.main.states.run_section.process']);
	});

	it('does not run the cross file checks when the shape is wrong', () => {
		expect(parseWorkflow({ manifest: { ...manifest, entry: 'other', schema: 'old' }, processes: workflow.processes }).ok).toBe(false);
		expect(issuePaths({ manifest: { ...manifest, entry: 'other', schema: 'old' }, processes: workflow.processes })).toEqual(['manifest.schema']);
	});

	it('reports a problem at the very top of the input as the root', () => {
		expect(parseWorkflow(null)).toMatchObject({ ok: false, issues: [{ path: '(root)' }] });
	});
});

// Returns the paths of the warnings from a valid workflow, or null when it has errors.
function warningPaths(input: unknown): string[] | null {
	const result = parseWorkflow(input);
	return result.ok ? result.warnings.map((warning) => warning.path) : null;
}

describe('warnings with the real examples', () => {
	it('gives the change of address workflow no warnings', () => {
		const example = exampleWorkflows().find((candidate) => candidate.name === 'change_of_address');
		expect(warningPaths({ manifest: example?.manifest, processes: example?.processes })).toEqual([]);
	});

	it('warns about the one state that nothing leads to in maternity allowance, without failing it', () => {
		const example = exampleWorkflows().find((candidate) => candidate.name === 'maternity_allowance');
		const result = parseWorkflow({ manifest: example?.manifest, processes: example?.processes });
		expect(result.ok).toBe(true);
		expect(warningPaths({ manifest: example?.manifest, processes: example?.processes })).toEqual([
			'processes.maternity_allowance.states.end_exception'
		]);
	});
});

describe('process warnings', () => {
	it('gives a valid process with every state in use no warnings', () => {
		const result = parseProcess(process);
		expect(result).toMatchObject({ ok: true, warnings: [] });
	});

	it('warns about a state that no route leads to', () => {
		const states = { ...process.states, orphan: { state_type: 'end', status: 'failed' } };
		const result = parseProcess({ ...process, states });
		expect(result).toMatchObject({ ok: true, warnings: [{ path: 'states.orphan' }] });
	});

	it('gives no warnings when the process has errors', () => {
		const result = parseProcess({ ...process, start: 'missing' });
		expect(result).not.toHaveProperty('warnings');
	});
});

describe('workflow warnings', () => {
	const spare = { ...workflow.processes.section, process_id: 'spare' };
	const withSpare = {
		manifest: { ...manifest, processes: [...manifest.processes, { process_id: 'spare', version: '0.1.0' }] },
		processes: { ...workflow.processes, spare }
	};

	it('gives a valid workflow no warnings', () => {
		expect(warningPaths(workflow)).toEqual([]);
	});

	it('warns about a process that no state runs', () => {
		expect(warningPaths(withSpare)).toEqual(['processes.spare']);
	});

	it('warns about a process that is only run from a state that nothing leads to', () => {
		const main = {
			...workflow.processes.main,
			states: { ...workflow.processes.main.states, hidden: { state_type: 'invoke', process: 'spare', next: 'finish' } }
		};
		const result = warningPaths({ ...withSpare, processes: { ...withSpare.processes, main } });
		expect(result).toEqual(['processes.main.states.hidden', 'processes.spare']);
	});

	it('warns about a state that nothing leads to inside a process, with the process name in the path', () => {
		const section = { ...workflow.processes.section, states: { ...workflow.processes.section.states, orphan: finish } };
		expect(warningPaths({ ...workflow, processes: { ...workflow.processes, section } })).toEqual([
			'processes.section.states.orphan'
		]);
	});

	describe('invoke catch names', () => {
		// The section ends with the outcome "cancelled", and the main process catches names from it.
		const section = {
			...workflow.processes.section,
			states: { finish: { state_type: 'end', status: 'cancelled', outcome: 'cancelled' } }
		};
		const withCatch = (on: string) => ({
			...workflow,
			processes: {
				main: {
					...workflow.processes.main,
					states: {
						run_section: { state_type: 'invoke', process: 'section', catch: [{ on, next: 'finish' }], next: 'finish' },
						finish
					}
				},
				section
			}
		});

		it('accepts a name that matches an end outcome of the sub process', () => {
			expect(warningPaths(withCatch('cancelled'))).toEqual([]);
		});

		it('accepts the name any', () => {
			expect(warningPaths(withCatch('any'))).toEqual([]);
		});

		it('warns about a name that matches no end outcome', () => {
			expect(warningPaths(withCatch('rejected'))).toEqual(['processes.main.states.run_section.catch.0.on']);
		});
	});

	it('gives no warnings when the workflow has errors', () => {
		const result = parseWorkflow({ ...workflow, manifest: { ...manifest, entry: 'other' } });
		expect(result).not.toHaveProperty('warnings');
	});
});

// Treats a plain test object as a workflow that is being edited. The cast is needed because each test builds only the keys it uses.
const editing = (value: unknown) => value as WorkingWorkflow;

describe('checkBeforeProceeding', () => {
	it('does not stop a workflow whose owner and contact are not set yet, because the policy review asks for them', () => {
		const notSet = { ...workflow, manifest: { ...workflow.manifest, owner: null, contact: null } };
		expect(parseWorkflow(notSet).ok).toBe(true);
		expect(checkBeforeProceeding(editing(notSet))).toEqual([]);
	});

	it('does not stop a workflow that has no owner or contact key at all', () => {
		const { owner: _owner, contact: _contact, ...rest } = workflow.manifest;
		const missing = { ...workflow, manifest: rest };
		expect(parseWorkflow(missing).ok).toBe(true);
		expect(checkBeforeProceeding(editing(missing))).toEqual([]);
	});

	it('gives a complete journey no problems', () => {
		expect(checkBeforeProceeding(editing(workflow))).toEqual([]);
	});

	it('reports a step with nothing after it once, in plain words', () => {
		const { next: _removed, ...unfinished } = workflow.processes.main.states.run_section;
		const main = { ...workflow.processes.main, states: { ...workflow.processes.main.states, run_section: unfinished } };
		const problems = checkBeforeProceeding(editing({ ...workflow, processes: { ...workflow.processes, main } }));

		expect(problems).toEqual([
			{ path: 'processes.main.states.run_section.next', message: 'run_section has nothing after it' },
			{ path: 'processes.main.states.finish', message: 'finish is not joined to the journey' }
		]);
	});

	it('reports a journey with no start once, in plain words, and the first state of each piece left loose', () => {
		const { start: _removed, ...noStart } = workflow.processes.section;
		const problems = checkBeforeProceeding(editing({ ...workflow, processes: { ...workflow.processes, section: noStart } }));

		expect(problems[0]).toEqual({ path: 'processes.section.start', message: expect.stringContaining('The journey has no start') });
		expect(problems.filter((problem) => problem.path === 'processes.section.start')).toHaveLength(1);
		expect(problems.slice(1).every((problem) => problem.message.endsWith('is not joined to the journey'))).toBe(true);
	});

	it('reports each way out of a decision that leads nowhere once, in plain words', () => {
		const decide = { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'ok' } }] };
		const section = { ...workflow.processes.section, start: 'decide', states: { decide, finish } };
		const problems = checkBeforeProceeding(editing({ ...workflow, processes: { ...workflow.processes, section } }));

		expect(problems).toEqual([
			{ path: 'processes.section.states.decide.rules.0.next', message: 'decide has 2 ways out that lead nowhere' },
			{ path: 'processes.section.states.finish', message: 'finish is not joined to the journey' }
		]);
	});

	it('reports a piece that is not joined to the start, even though the schema accepts it', () => {
		const section = { ...workflow.processes.section, states: { ...workflow.processes.section.states, loose: finish } };
		const problems = checkBeforeProceeding(editing({ ...workflow, processes: { ...workflow.processes, section } }));

		expect(problems.map((problem) => problem.path)).toEqual(['processes.section.states.loose']);
	});

	it('lists the schema problems as well, all at once', () => {
		const main = { ...workflow.processes.main, states: { ...workflow.processes.main.states, run_section: { state_type: 'invoke', process: 'gone', next: 'missing' } } };
		const paths = checkBeforeProceeding(editing({ ...workflow, processes: { ...workflow.processes, main } })).map((problem) => problem.path);

		expect(paths).toEqual(expect.arrayContaining(['processes.main.states.run_section.next', 'processes.main.states.run_section.process']));
	});

	it('leaves out warnings that do not stop a journey being passed on, such as a process nothing runs', () => {
		const spare = { ...workflow.processes.section, process_id: 'spare' };
		const withSpare = {
			manifest: { ...manifest, processes: [...manifest.processes, { process_id: 'spare', version: '0.1.0' }] },
			processes: { ...workflow.processes, spare }
		};
		expect(checkBeforeProceeding(editing(withSpare))).toEqual([]);
	});
});

describe('journeyErrors', () => {
	// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
	const build = (start: string | undefined, states: Record<string, unknown>) =>
		({ process_id: 'p', version: '0.1.0', vars: {}, ...(start ? { start } : {}), states }) as unknown as WorkingProcess;
	const wait = (next?: string) => ({ state_type: 'wait', duration: 'PT1S', ...(next ? { next } : {}) });
	const finish = { state_type: 'end', status: 'success' };

	it('finds nothing in any of the form examples', () => {
		for (const example of formExamples) {
			for (const each of Object.values(example.workflow?.processes ?? {})) expect(journeyErrors(each), example.slug).toEqual([]);
		}
	});

	it('names only the first state of a loose piece, not every state cut off behind it', () => {
		const process = build('a', { a: wait('end'), b: wait('c'), c: wait('d'), d: wait('end'), end: finish });
		expect(journeyErrors(process)).toMatchObject([{ path: 'states.b', state: 'b', message: 'is not joined to the journey' }]);
	});

	it('names a loose loop once, by its first state', () => {
		const process = build('a', { a: wait('end'), b: wait('c'), c: wait('b'), end: finish });
		expect(journeyErrors(process)).toMatchObject([{ path: 'states.b', state: 'b', message: 'is not joined to the journey' }]);
	});

	it('says once that the journey has no start, without naming every state as loose', () => {
		const problems = journeyErrors(build(undefined, { a: wait('b'), b: wait('end'), end: finish }));
		expect(problems).toMatchObject([
			{ path: 'start', kind: 'no_start', title: 'No start' },
			{ path: 'states.a', state: 'a', message: 'is not joined to the journey' }
		]);
	});

	it('says a step has nothing after it, in its own words and not the schema words as well', () => {
		expect(journeyErrors(build('a', { a: wait(), end: finish }))).toMatchObject([
			{ path: 'states.a.next', state: 'a', kind: 'no_next', message: 'has nothing after it', title: 'No next step' },
			{ path: 'states.end', state: 'end', message: 'is not joined to the journey' }
		]);
	});

	it('names the state a schema problem is about, when it is about one', () => {
		const problems = journeyErrors(build('a', { a: wait('missing'), end: finish }));
		expect(problems).toContainEqual(
			expect.objectContaining({ path: 'states.a.next', state: 'a', kind: 'schema', fix: expect.stringContaining('missing') })
		);
	});

	it('gives a decision whose ways out lead nowhere one problem, with a title that counts them', () => {
		const decide = { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'x' } }], default: undefined };
		const [problem] = journeyErrors(build('decide', { decide }));
		expect(problem).toMatchObject({ state: 'decide', kind: 'way_out_leads_nowhere', title: '2 ways out lead nowhere' });
	});
});

describe('journeyWarnings', () => {
	const build = (states: Record<string, unknown>) =>
		({ process_id: 'p', version: '0.1.0', vars: {}, start: Object.keys(states)[0], states }) as unknown as WorkingProcess;

	it('lists placeholder words left in a question or a message, and rules still to be confirmed', () => {
		const process = build({
			ask: { ...placeholderInput('ask'), state_type: 'input', next: 'say' },
			say: { ...placeholderOutput(), state_type: 'output', next: 'decide' },
			decide: { state_type: 'choice', rules: [{ when: undecidedRule, next: 'end' }, { when: undecidedRule, next: 'end' }], default: 'end' },
			end: { state_type: 'end', status: 'success' }
		});
		expect(journeyWarnings(process).map((warning) => [warning.state, warning.kind, warning.message, warning.title])).toEqual([
			['ask', 'placeholder_question', `still has the placeholder question "${placeholderQuestion}"`, 'Placeholder question'],
			['say', 'placeholder_message', `still has the placeholder message "${placeholderMessage}"`, 'Placeholder message'],
			['decide', 'rule_to_confirm', 'has 2 rules still to be confirmed', '2 rules to be confirmed']
		]);
		expect(journeyWarnings(process)[0].fix).toContain(placeholderQuestion);
	});

	it('does not list the placeholders a later review fills in, such as the details of a call', () => {
		const process = build({
			call: { state_type: 'api_call', ...unconnectedApiCallDetails, next: 'end' },
			end: { state_type: 'end', status: 'success' }
		});
		expect(journeyWarnings(process)).toEqual([]);
	});

	it('finds nothing in any of the form examples', () => {
		for (const example of formExamples) {
			for (const each of Object.values(example.workflow?.processes ?? {})) expect(journeyWarnings(each), example.slug).toEqual([]);
		}
	});
});
