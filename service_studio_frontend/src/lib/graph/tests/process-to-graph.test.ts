import { describe, expect, it } from 'vitest';
import { workflowExamples } from '$lib/examples/workflows';
import type { Process } from '$lib/schema/workflow/process';
import { routesOf } from '$lib/schema/workflow/routes';
import { processToGraph, startNodeId } from '../process-to-graph';

const finish = { type: 'end', status: 'success' };
const isTrue = { op: 'is_true', path: 'a' };

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

describe('processToGraph with the real examples', () => {
	const processes = workflowExamples.flatMap((example) => Object.values(example.workflow?.processes ?? {}));

	it('builds a graph for every process in both examples', () => {
		expect(processes).toHaveLength(14);
	});

	it('makes one node per state plus the start dot, and one edge per route plus the start edge', () => {
		for (const process of processes) {
			const graph = processToGraph(process);
			const routeCount = Object.values(process.states).flatMap((state) => routesOf(state)).length;

			expect(graph.nodes, process.process_id).toHaveLength(Object.keys(process.states).length + 1);
			expect(graph.edges, process.process_id).toHaveLength(routeCount + 1);
		}
	});

	it('gives every node and edge a unique id and joins every edge to nodes that exist', () => {
		for (const process of processes) {
			const { nodes, edges } = processToGraph(process);
			const nodeIds = new Set(nodes.map((node) => node.id));

			expect(nodeIds.size, process.process_id).toBe(nodes.length);
			expect(new Set(edges.map((edge) => edge.id)).size, process.process_id).toBe(edges.length);
			for (const edge of edges) {
				expect(nodeIds.has(edge.source), edge.id).toBe(true);
				expect(nodeIds.has(edge.target), edge.id).toBe(true);
			}
		}
	});

	it('starts with the start dot and then the start state of the process', () => {
		for (const process of processes) {
			const { nodes } = processToGraph(process);
			expect(nodes[0].id).toBe(startNodeId);
			expect(nodes[1].id).toBe(process.start);
		}
	});
});

describe('processToGraph nodes', () => {
	const process = build('ask', {
		ask: { type: 'input', prompt: 'Is your address correct?', schema: { kind: 'boolean' }, assign: 'ok', next: 'check' },
		check: {
			type: 'choice',
			name: 'Address correct?',
			rules: [{ when: isTrue, next: 'say_thanks' }],
			default: 'look_up_address'
		},
		look_up_address: { type: 'call', method: 'GET', service: 'dvla', url: '/x', next: 'finish' },
		say_thanks: { type: 'output', channel: 'transcript', message: 'Thank you.', next: 'finish' },
		finish: { type: 'end', status: 'success', outcome: 'address_confirmed' }
	});
	const { nodes } = processToGraph(process);
	const node = (id: string) => nodes.find((candidate) => candidate.id === id)!;

	it('uses the question as the title of an input', () => {
		expect(node('ask').data).toMatchObject({ title: 'Is your address correct?', stepNumber: 1, stateType: 'input' });
	});

	it('uses the message as the title of an output', () => {
		expect(node('say_thanks').data).toMatchObject({ title: 'Thank you.', stateType: 'output' });
	});

	it('tidies the code into words for a state with no text of its own', () => {
		expect(node('look_up_address').data).toMatchObject({ title: 'Look up address', stateType: 'call' });
	});

	it('prefers a name written by the author to the state text', () => {
		const named = processToGraph(
			build('ask', {
				ask: { type: 'input', name: 'Confirm address', prompt: 'Is it right?', schema: { kind: 'boolean' }, assign: 'ok', next: 'finish' },
				finish
			})
		);
		expect(named.nodes[1].data).toMatchObject({ title: 'Confirm address' });
	});

	it('draws a choice as a diamond and an end as a dot', () => {
		expect(node('check')).toMatchObject({ type: 'condition', data: { title: 'Address correct?' } });
		expect(node('finish')).toMatchObject({
			type: 'terminal',
			data: { appearance: 'end', status: 'success', stateId: 'finish', ariaLabel: 'Journey end, Address confirmed' }
		});
	});

	it('numbers only the boxes, in journey order with a choice rule before its default', () => {
		const numbered = nodes.flatMap((candidate) => (candidate.type === 'step' ? [[candidate.id, candidate.data.stepNumber]] : []));
		expect(numbered).toEqual([
			['ask', 1],
			['say_thanks', 2],
			['look_up_address', 3]
		]);
	});

	it('gives each box a size that fits its title', () => {
		const step = node('ask');
		expect(step.type === 'step' && step.data.width).toBeGreaterThanOrEqual(260);
		expect(step.type === 'step' && step.data.height).toBeGreaterThanOrEqual(56);
	});

	it('words the label read by a screen reader from the number and the title', () => {
		expect(node('ask').data.ariaLabel).toBe('Step 1, Is your address correct?');
		expect(node('check').data.ariaLabel).toBe('Decision, Address correct?');
	});

	it('lists a state that nothing leads to last, still numbered', () => {
		const withOrphan = processToGraph(build('a', { a: { type: 'wait', duration: 'PT1S', next: 'done' }, orphan_step: { type: 'wait', duration: 'PT1S', next: 'done' }, done: finish }));
		expect(withOrphan.nodes.map((candidate) => candidate.id)).toEqual([startNodeId, 'a', 'done', 'orphan_step']);
	});
});

describe('processToGraph edges', () => {
	const process = build('ask', {
		ask: {
			type: 'input',
			prompt: 'Name?',
			schema: { kind: 'string' },
			assign: 'name',
			next: 'branch',
			on_invalid: 'ask',
			timeout: { after: 'PT5S', next: 'finish' }
		},
		branch: { type: 'choice', rules: [{ when: isTrue, next: 'call' }], default: 'finish' },
		call: { type: 'call', method: 'GET', service: 'dvla', url: '/x', catch: [{ on: 'any', next: 'finish' }], next: 'finish' },
		finish
	});
	const { edges } = processToGraph(process);

	it('starts from the start dot', () => {
		expect(edges[0]).toMatchObject({ source: startNodeId, target: 'ask', data: { kind: 'start' } });
	});

	it('gives each route the kind it belongs to', () => {
		const kinds = edges.map((edge) => [edge.source, edge.target, edge.data?.kind]);
		expect(kinds).toEqual([
			[startNodeId, 'ask', 'start'],
			['ask', 'branch', 'next'],
			['ask', 'ask', 'on_invalid'],
			['ask', 'finish', 'timeout'],
			['branch', 'call', 'rule'],
			['branch', 'finish', 'default'],
			['call', 'finish', 'next'],
			['call', 'finish', 'catch']
		]);
	});

	it('keeps two routes to the same state apart with different ids', () => {
		const toFinish = edges.filter((edge) => edge.source === 'call' && edge.target === 'finish');
		expect(toFinish.map((edge) => edge.id)).toEqual(['call:next', 'call:catch.0.next']);
	});

	it('draws no edge for a route to a state that does not exist or a start that does not exist', () => {
		const half = processToGraph(build('a', { a: { type: 'wait', duration: 'PT1S', next: 'missing' } }));
		expect(half.edges).toHaveLength(1);

		const noStart = processToGraph(build('nowhere', { a: finish }));
		expect(noStart.edges).toEqual([]);
	});
});
