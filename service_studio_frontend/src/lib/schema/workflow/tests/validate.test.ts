import { describe, expect, it } from 'vitest';
import { exampleProcessFiles, exampleWorkflows } from './example-states';
import { parseProcess, parseWorkflow } from '../validate';

// A small valid process that each test copies and then breaks in one way.
const process = {
	process_id: 'check_attendance',
	version: '0.1.0',
	start: 'ask',
	vars: { attended: null },
	states: {
		ask: {
			type: 'input',
			prompt: 'Did you attend?',
			schema: { kind: 'boolean' },
			assign: 'attended',
			next: 'branch'
		},
		branch: {
			type: 'choice',
			rules: [{ when: { op: 'is_true', path: 'attended' }, next: 'finish' }],
			default: 'ask'
		},
		finish: { type: 'end', status: 'success' }
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
		const broken = { ...process, states: { ...process.states, finish: { type: 'end' } } };
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
				type: 'choice',
				rules: [{ when: { op: 'is_true', path: 'attended' }, next: 'gone_rule' }],
				default: 'gone_default'
			}
		};
		const result = parseProcess({ ...process, states });
		const paths = !result.ok ? result.issues.map((issue) => issue.path) : [];
		expect(paths).toEqual(['states.ask.timeout.next', 'states.branch.rules.0.next', 'states.branch.default']);
	});

	it('reports a missing target inside a catch clause', () => {
		const call = { type: 'call', method: 'GET', service: 'dwp', url: '/x', catch: [{ on: 'any', next: 'gone' }], next: 'finish' };
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
		const result = parseProcess({ ...process, states: { ask: { type: 'input' } } });
		expect(result.ok).toBe(false);
	});
});

// A small valid workflow of two processes: the entry process runs a section and carries on.
const manifest = {
	workflow_id: 1,
	schema: 'sfsm/0.2',
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

const finish = { type: 'end', status: 'success' };

const workflow = {
	manifest,
	processes: {
		main: {
			process_id: 'main',
			version: '0.1.0',
			start: 'run_section',
			vars: {},
			states: { run_section: { type: 'invoke', process: 'section', next: 'finish' }, finish }
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
		const states = { run_section: { type: 'invoke', process: 'section', next: 'nowhere' }, finish };
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
		const states = { run_section: { type: 'invoke', process: 'missing', next: 'finish' }, finish };
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
		const states = { ...process.states, orphan: { type: 'end', status: 'failed' } };
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
			states: { ...workflow.processes.main.states, hidden: { type: 'invoke', process: 'spare', next: 'finish' } }
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
			states: { finish: { type: 'end', status: 'cancelled', outcome: 'cancelled' } }
		};
		const withCatch = (on: string) => ({
			...workflow,
			processes: {
				main: {
					...workflow.processes.main,
					states: {
						run_section: { type: 'invoke', process: 'section', catch: [{ on, next: 'finish' }], next: 'finish' },
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
