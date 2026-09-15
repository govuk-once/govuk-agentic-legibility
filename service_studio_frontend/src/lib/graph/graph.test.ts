import { describe, expect, it } from 'vitest';
import type { Service, ServiceStep } from '$lib/schema';
import { serviceToGraph } from './service-to-graph';
import { layoutJourneyGraph } from './layout';

/**
 * Builds a service step with sensible defaults so a test only has to state the parts it cares about.
 */
function step(partial: Partial<ServiceStep> & { id: string }): ServiceStep {
	return {
		id: partial.id,
		type: partial.type ?? { kind: 'info', body: '' },
		name: partial.name ?? partial.id,
		description: partial.description ?? '',
		fields: partial.fields ?? [],
		transitions: partial.transitions ?? []
	};
}

/**
 * Wraps a list of steps in the surrounding service metadata, defaulting the entry point to the first step.
 */
function makeService(steps: ServiceStep[], startStepId = steps[0]?.id ?? ''): Service {
	return {
		id: '00000000-0000-4000-8000-000000000000',
		version: 1,
		state: 'draft',
		name: 'Test service',
		owner: 'gds',
		contact: 'test@example.com',
		description: '',
		descriptionPublic: '',
		startStepId,
		steps
	};
}

describe('serviceToGraph', () => {
	it('builds one node per step plus start and end for a linear service', () => {
		const graph = serviceToGraph(
			makeService([
				step({ id: 'a', transitions: [{ targetStepId: 'b' }] }),
				step({ id: 'b', transitions: [{ targetStepId: 'c' }] }),
				step({ id: 'c' })
			])
		);

		expect(graph.nodes.filter((node) => node.type === 'step')).toHaveLength(3);
		expect(graph.nodes.filter((node) => node.type === 'terminal')).toHaveLength(2);
		expect(graph.nodes.some((node) => node.id === 'start')).toBe(true);
		expect(graph.nodes.some((node) => node.id === 'end')).toBe(true);
		expect(graph.edges).toHaveLength(4);
	});

	it('inserts a gateway with one branch edge per transition when a step has several', () => {
		const graph = serviceToGraph(
			makeService([
				step({
					id: 'a',
					transitions: [
						{ targetStepId: 'b', label: 'Yes' },
						{ targetStepId: 'c', condition: { all: [{ field: 'x', operator: 'equals', value: 'y' }] } },
						{ targetStepId: 'd' }
					]
				}),
				step({ id: 'b' }),
				step({ id: 'c' }),
				step({ id: 'd' })
			])
		);

		const gateway = graph.nodes.find((node) => node.type === 'condition');
		expect(gateway).toBeDefined();
		expect(graph.edges.some((edge) => edge.source === 'a' && edge.target === gateway?.id)).toBe(true);

		const branchEdges = graph.edges.filter((edge) => edge.kind === 'branch');
		expect(branchEdges).toHaveLength(3);

		const toB = branchEdges.find((edge) => edge.target === 'b');
		expect(toB?.label).toBe('Yes');
		expect(toB?.tagColour).toBe('grey');

		const toC = branchEdges.find((edge) => edge.target === 'c');
		expect(toC?.label).toBe('x = y');

		const toD = branchEdges.find((edge) => edge.target === 'd');
		expect(toD?.label).toBeUndefined();
		expect(toD?.tagColour).toBeUndefined();
	});

	it('labels the gateway with the best question wording it can find on the step', () => {
		const twoTransitions = [{ targetStepId: 'x' }, { targetStepId: 'y' }];
		const targets = [step({ id: 'x' }), step({ id: 'y' })];

		const namedQuestion = serviceToGraph(
			makeService([step({ id: 'a', name: 'Has your baby been born?', transitions: twoTransitions }), ...targets])
		);
		const fieldQuestion = serviceToGraph(
			makeService([
				step({
					id: 'a',
					name: 'Choose how to enter your address',
					fields: [
						{ id: 'f', name: 'method', label: 'How do you want to enter your address?', element: 'radio' }
					],
					transitions: twoTransitions
				}),
				...targets
			])
		);
		const noQuestion = serviceToGraph(
			makeService([step({ id: 'a', name: 'Choose a route', transitions: twoTransitions }), ...targets])
		);

		const question = (graph: ReturnType<typeof serviceToGraph>) => {
			const gateway = graph.nodes.find((node) => node.type === 'condition');
			return gateway?.type === 'condition' ? gateway.data.question : undefined;
		};

		expect(question(namedQuestion)).toBe('Has your baby been born?');
		expect(question(fieldQuestion)).toBe('How do you want to enter your address?');
		expect(question(noQuestion)).toBe('Which route applies?');
	});

	it('joins a step with no transitions to the end node', () => {
		const graph = serviceToGraph(
			makeService([step({ id: 'a', transitions: [{ targetStepId: 'b' }] }), step({ id: 'b' })])
		);

		expect(graph.edges.some((edge) => edge.source === 'b' && edge.target === 'end')).toBe(true);
	});

	it('connects the start node to the service startStepId', () => {
		const graph = serviceToGraph(
			makeService(
				[step({ id: 'a' }), step({ id: 'b', transitions: [{ targetStepId: 'a' }] })],
				'b'
			)
		);

		expect(graph.edges.some((edge) => edge.source === 'start' && edge.target === 'b')).toBe(true);
	});

	it('sizes a step node from its title, so a long title gives a wider and taller node', () => {
		const graph = serviceToGraph(
			makeService([
				step({ id: 'short', name: 'Pay' }),
				step({
					id: 'long',
					name: 'Check every detail of your application before you send it to us for a decision'
				})
			])
		);

		const shortNode = graph.nodes.find((node) => node.id === 'short');
		const longNode = graph.nodes.find((node) => node.id === 'long');

		expect(shortNode?.type).toBe('step');
		expect(longNode?.type).toBe('step');
		if (shortNode?.type === 'step' && longNode?.type === 'step') {
			expect(longNode.data.width).toBeGreaterThan(shortNode.data.width);
			expect(longNode.data.height).toBeGreaterThan(shortNode.data.height);
		}
	});
});

describe('journey graph layout', () => {
	it('positions the start before the end and returns positive dimensions', () => {
		const graph = serviceToGraph(
			makeService([step({ id: 'a', transitions: [{ targetStepId: 'b' }] }), step({ id: 'b' })])
		);
		const { nodes, width, height } = layoutJourneyGraph(graph.nodes, graph.edges);
		const start = nodes.find((node) => node.id === 'start');
		const end = nodes.find((node) => node.id === 'end');

		expect(start?.position.y).toBeLessThan(end?.position.y ?? 0);
		expect(nodes.every((node) => Number.isFinite(node.position.x))).toBe(true);
		expect(width).toBeGreaterThan(0);
		expect(height).toBeGreaterThan(0);
	});

	it('keeps a fork apart from an unrelated fork when their outcomes both reconverge', () => {
		// Mirrors the shape that produced overlapping nodes on the 61 step maternity example at minimal
		// scale: two forks, each with two outcomes, all four outcomes rejoining at one shared step.
		const graph = serviceToGraph(
			makeService([
				step({ id: 'a', transitions: [{ targetStepId: 'p' }, { targetStepId: 'q' }] }),
				step({ id: 'p', transitions: [{ targetStepId: 'p1' }, { targetStepId: 'p2' }] }),
				step({ id: 'q', transitions: [{ targetStepId: 'q1' }, { targetStepId: 'q2' }] }),
				step({ id: 'p1', transitions: [{ targetStepId: 'merge' }] }),
				step({ id: 'p2', transitions: [{ targetStepId: 'merge' }] }),
				step({ id: 'q1', transitions: [{ targetStepId: 'merge' }] }),
				step({ id: 'q2', transitions: [{ targetStepId: 'merge' }] }),
				step({ id: 'merge' })
			])
		);

		const { nodes } = layoutJourneyGraph(graph.nodes, graph.edges);
		const positionOf = (id: string) => nodes.find((node) => node.id === id)?.position ?? { x: 0, y: 0 };

		// No two nodes should land in exactly the same place.
		const positions = nodes.map((node) => `${node.position.x},${node.position.y}`);
		expect(new Set(positions).size).toBe(positions.length);

		// p's own two outcomes should sit next to each other in the rank, and q's own two outcomes should
		// sit next to each other, rather than interleaved (p, q, p, q), which is what a layout with no
		// crossing reduction would produce. Node width and gap are uniform here, so comparing raw distance
		// would not tell the two cases apart, adjacent nodes are the same distance apart either way, only
		// which nodes are adjacent to which reveals whether the outcomes stayed grouped.
		const order = ['p1', 'p2', 'q1', 'q2']
			.map((id) => ({ letter: id[0], x: positionOf(id).x }))
			.sort((a, b) => a.x - b.x)
			.map((entry) => entry.letter)
			.join('');
		expect(['ppqq', 'qqpp']).toContain(order);
	});

	it('lays out a service that loops back to an earlier step without hanging', () => {
		const graph = serviceToGraph(
			makeService([
				step({ id: 'ask', transitions: [{ targetStepId: 'check' }] }),
				step({
					id: 'check',
					transitions: [
						{ targetStepId: 'done', label: 'Valid' },
						{ targetStepId: 'ask', label: 'Invalid, try again' }
					]
				}),
				step({ id: 'done' })
			])
		);

		const { nodes } = layoutJourneyGraph(graph.nodes, graph.edges);

		expect(nodes.every((node) => Number.isFinite(node.position.x) && Number.isFinite(node.position.y))).toBe(
			true
		);
	});

	it('still lays out a step that nothing points to', () => {
		const graph = serviceToGraph(
			makeService([
				step({ id: 'a', transitions: [{ targetStepId: 'b' }] }),
				step({ id: 'b' }),
				// Nothing transitions to this step and it is not startStepId, mirroring a step left orphaned
				// by an earlier edit rather than a genuine cycle.
				step({ id: 'orphan' })
			])
		);

		const { nodes } = layoutJourneyGraph(graph.nodes, graph.edges);

		expect(nodes.every((node) => Number.isFinite(node.position.x) && Number.isFinite(node.position.y))).toBe(
			true
		);
	});
});
