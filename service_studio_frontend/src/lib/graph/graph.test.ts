import { describe, expect, it } from 'vitest';
import { addressChangeBranchDecoration, initialSteps } from '$lib/journey/steps';
import type { JourneyStep } from '$lib/journey/types';
import { createJourneyGraph } from './build-journey-graph';
import { layoutJourneyGraph } from './layout';

describe('journey graph builder', () => {
	it('shows every step in one sequence when branching is hidden', () => {
		const graph = createJourneyGraph(initialSteps, false, addressChangeBranchDecoration);

		expect(graph.nodes).toHaveLength(initialSteps.length + 2);
		expect(graph.nodes.some((node) => node.type === 'condition')).toBe(false);
		expect(graph.edges).toHaveLength(initialSteps.length + 1);
		expect(graph.edges.every((edge) => edge.label === undefined)).toBe(true);
	});

	it('uses labelled edges for the two branch outcomes', () => {
		const graph = createJourneyGraph(initialSteps, true, addressChangeBranchDecoration);
		const branchLabels = graph.edges.flatMap((edge) => (edge.label ? [edge.label] : []));
		const branchEdges = graph.edges.filter((edge) => edge.type === 'branch');

		expect(branchLabels).toEqual(['Postcode', 'Manual']);
		expect(branchEdges.map((edge) => edge.data)).toEqual([{ tagColour: 'grey' }, { tagColour: 'grey' }]);
		expect(branchEdges.every((edge) => edge.markerEnd && typeof edge.markerEnd !== 'string')).toBe(true);
		expect(graph.nodes.some((node) => node.type === 'condition')).toBe(true);
	});

	it('falls back to a plain sequence when there are not enough steps to form the branch', () => {
		const tooFewSteps = initialSteps.slice(0, 3);
		const graph = createJourneyGraph(tooFewSteps, true, addressChangeBranchDecoration);

		expect(graph.nodes.some((node) => node.type === 'condition')).toBe(false);
		expect(graph.nodes).toHaveLength(tooFewSteps.length + 2);
	});

	it('follows the steps currently at the branch position, so reordering also reorders the graph', () => {
		// Swap the first two steps, which used to be the anchor and one of its own branch outcomes.
		const reordered: JourneyStep[] = [initialSteps[1], initialSteps[0], initialSteps[2], initialSteps[3]];
		const graph = createJourneyGraph(reordered, true, addressChangeBranchDecoration);

		const anchorCondition = graph.edges.find((edge) => edge.id === 'anchor-condition');
		const branchEdges = graph.edges.filter((edge) => edge.type === 'branch');

		expect(anchorCondition?.source).toBe(reordered[0].id);
		expect(branchEdges.map((edge) => edge.target)).toEqual([reordered[1].id, reordered[2].id]);
	});
});

describe('journey graph node sizing', () => {
	it('gives a step with a longer description a taller box than one with a short description', () => {
		const shortStep: JourneyStep = { ...initialSteps[0], id: 'short', description: 'Short' };
		const longStep: JourneyStep = {
			...initialSteps[0],
			id: 'long',
			description: 'A considerably longer description that will need to wrap onto more than one line'
		};

		const graph = createJourneyGraph([shortStep, longStep], false, addressChangeBranchDecoration);
		const shortNode = graph.nodes.find((node) => node.id === 'short');
		const longNode = graph.nodes.find((node) => node.id === 'long');

		expect(shortNode?.type).toBe('step');
		expect(longNode?.type).toBe('step');
		if (shortNode?.type === 'step' && longNode?.type === 'step') {
			expect(longNode.data.height).toBeGreaterThan(shortNode.data.height);
		}
	});
});

describe('journey graph layout', () => {
	it('positions the start before the end without changing the connections', () => {
		const graph = createJourneyGraph(initialSteps, true, addressChangeBranchDecoration);
		const edgeCountBeforeLayout = graph.edges.length;
		const nodes = layoutJourneyGraph(graph.nodes, graph.edges);
		const start = nodes.find((node) => node.id === 'start');
		const end = nodes.find((node) => node.id === 'end');

		expect(start?.position.y).toBeLessThan(end?.position.y ?? 0);
		expect(nodes.every((node) => Number.isFinite(node.position.x))).toBe(true);
		expect(graph.edges).toHaveLength(edgeCountBeforeLayout);
	});
});
