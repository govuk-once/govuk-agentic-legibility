import { describe, expect, it } from 'vitest';
import { exampleWorkflows } from './example-states';
import { manifestSchema, workflowSchema } from '../workflow';

describe('workflowSchema with the real examples', () => {
	const workflows = exampleWorkflows();

	it('finds both example services', () => {
		expect(workflows.map((workflow) => workflow.name).sort()).toEqual(['change_of_address', 'maternity_allowance']);
	});

	it.each(['change_of_address', 'maternity_allowance'])('accepts the manifest of %s', (name) => {
		const workflow = workflows.find((candidate) => candidate.name === name);
		const result = manifestSchema.safeParse(workflow?.manifest);
		expect(result.success, JSON.stringify(result.error?.issues.slice(0, 3))).toBe(true);
	});

	it.each(['change_of_address', 'maternity_allowance'])('accepts the assembled workflow of %s', (name) => {
		const workflow = workflows.find((candidate) => candidate.name === name);
		const result = workflowSchema.safeParse({ manifest: workflow?.manifest, processes: workflow?.processes });
		expect(result.success, JSON.stringify(result.error?.issues.slice(0, 3))).toBe(true);
	});
});

describe('manifestSchema', () => {
	const manifest = {
		workflow_id: 1,
		schema: 'sfsm/0.2',
		id: 'dvla.change_of_address',
		version: '0.1.0',
		owner: 'DVLA',
		contact: 'owner@example.gov.uk',
		description: 'Change of address journey.',
		state: 'draft',
		entry: 'change_of_address',
		executor: {
			workflow_id_template: 'coa-{{input.licence_no}}',
			id_reuse_policy: 'reject_duplicate',
			run_timeout: 'P14D',
			search_attributes: {}
		},
		defaults: { api_call: { timeouts: { start_to_close: 'PT15S' }, retry: { max_attempts: 3 } } },
		processes: [{ process_id: 'change_of_address', version: '0.1.0' }]
	};

	it('accepts a manifest', () => {
		expect(manifestSchema.safeParse(manifest).success).toBe(true);
	});

	it('accepts a text workflow_id, notes, and empty defaults', () => {
		const adjusted = { ...manifest, workflow_id: 'coa-1', metadata: { navigation: 'strict' }, defaults: {} };
		expect(manifestSchema.safeParse(adjusted).success).toBe(true);
	});

	it.each(['workflow_id', 'schema', 'id', 'version', 'owner', 'contact', 'description', 'state', 'entry', 'executor', 'defaults', 'processes'])(
		'rejects a manifest with no %s',
		(key) => {
			const { [key as keyof typeof manifest]: _removed, ...incomplete } = manifest;
			expect(manifestSchema.safeParse(incomplete).success).toBe(false);
		}
	);

	it('rejects a schema version other than sfsm/0.2', () => {
		expect(manifestSchema.safeParse({ ...manifest, schema: 'sfsm/0.1' }).success).toBe(false);
	});

	it('rejects an id with no namespace and an id with spaces', () => {
		expect(manifestSchema.safeParse({ ...manifest, id: 'change_of_address' }).success).toBe(false);
		expect(manifestSchema.safeParse({ ...manifest, id: 'dvla.change of address' }).success).toBe(false);
	});

	it('rejects a contact that is not an email address', () => {
		expect(manifestSchema.safeParse({ ...manifest, contact: 'the DVLA team' }).success).toBe(false);
	});

	it('rejects a state other than draft, live, deprecated or retired', () => {
		expect(manifestSchema.safeParse({ ...manifest, state: 'published' }).success).toBe(false);
	});

	it('rejects an executor with a bad reuse policy or run timeout', () => {
		const executor = manifest.executor;
		expect(manifestSchema.safeParse({ ...manifest, executor: { ...executor, id_reuse_policy: 'ignore' } }).success).toBe(false);
		expect(manifestSchema.safeParse({ ...manifest, executor: { ...executor, run_timeout: '14 days' } }).success).toBe(false);
	});

	it('rejects an empty process list and a process with a bad version', () => {
		expect(manifestSchema.safeParse({ ...manifest, processes: [] }).success).toBe(false);
		expect(manifestSchema.safeParse({ ...manifest, processes: [{ process_id: 'a', version: 'one' }] }).success).toBe(false);
	});

	it('rejects a key the document does not list', () => {
		expect(manifestSchema.safeParse({ ...manifest, category: 'transport' }).success).toBe(false);
	});
});

describe('workflowSchema', () => {
	it('rejects a workflow whose process is invalid', () => {
		const workflow = exampleWorkflows()[0];
		const processes = { ...workflow.processes, broken: { process_id: 'broken' } };
		expect(workflowSchema.safeParse({ manifest: workflow.manifest, processes }).success).toBe(false);
	});

	it('rejects a workflow with no manifest', () => {
		expect(workflowSchema.safeParse({ processes: {} }).success).toBe(false);
	});
});
