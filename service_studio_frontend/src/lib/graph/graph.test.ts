import { describe, expect, it } from 'vitest';
import { createDrivingLicenceGraph } from './driving-licence-fixture';
import { layoutJourneyGraph } from './layout';

describe('driving licence graph fixture', () => {
	it('shows every service step in one sequence when branching is hidden', () => {
		const graph = createDrivingLicenceGraph(false);

		expect(graph.nodes).toHaveLength(8);
		expect(graph.nodes.some((node) => node.type === 'condition')).toBe(false);
		expect(graph.edges).toHaveLength(7);
		expect(graph.edges.every((edge) => edge.label === undefined)).toBe(true);
	});

	it('uses labelled edges for the two branch outcomes', () => {
		const graph = createDrivingLicenceGraph(true);
		const branchLabels = graph.edges.flatMap((edge) => (edge.label ? [edge.label] : []));
		const branchEdges = graph.edges.filter((edge) => edge.type === 'branch');

		expect(branchLabels).toEqual(['No', 'Yes']);
		expect(branchEdges.map((edge) => edge.data)).toEqual([
			{ appearance: 'negative' },
			{ appearance: 'positive' }
		]);
		expect(branchEdges.every((edge) => edge.markerEnd && typeof edge.markerEnd !== 'string')).toBe(true);
		expect(branchEdges.map((edge) => edge.markerEnd)).toEqual([
			{ type: 'arrowclosed', color: '#505a5f' },
			{ type: 'arrowclosed', color: '#505a5f' }
		]);
		expect(graph.nodes.some((node) => node.type === 'condition')).toBe(true);
	});
});

describe('journey graph layout', () => {
	it('positions the start before the end without changing the connections', () => {
		const graph = createDrivingLicenceGraph(true);
		const nodes = layoutJourneyGraph(graph.nodes, graph.edges);
		const start = nodes.find((node) => node.id === 'start');
		const end = nodes.find((node) => node.id === 'end');

		expect(start?.position.y).toBeLessThan(end?.position.y ?? 0);
		expect(nodes.every((node) => Number.isFinite(node.position.x))).toBe(true);
		expect(graph.edges).toHaveLength(10);
	});
});
