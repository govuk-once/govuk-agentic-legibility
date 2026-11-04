import { describe, expect, it } from 'vitest';
import { workflowExamples } from '$lib/examples/workflows';
import { layoutJourneyGraph, nodeSize } from '../layout';
import { processToGraph } from '../process-to-graph';

const processes = workflowExamples.flatMap((example) => Object.values(example.workflow?.processes ?? {}));

describe('layoutJourneyGraph with process graphs', () => {
	it('gives every node of every real process a position', () => {
		for (const process of processes) {
			const { nodes, edges } = processToGraph(process);
			const laidOut = layoutJourneyGraph(nodes, edges);

			expect(laidOut.nodes, process.process_id).toHaveLength(nodes.length);
			for (const node of laidOut.nodes) {
				expect(Number.isFinite(node.position.x), `${process.process_id} ${node.id}`).toBe(true);
				expect(Number.isFinite(node.position.y), `${process.process_id} ${node.id}`).toBe(true);
			}
		}
	});

	it('keeps the nodes of every real process from overlapping', () => {
		for (const process of processes) {
			const { nodes, edges } = processToGraph(process);
			const { nodes: laidOut } = layoutJourneyGraph(nodes, edges);

			for (const [index, first] of laidOut.entries()) {
				for (const second of laidOut.slice(index + 1)) {
					const a = nodeSize(first);
					const b = nodeSize(second);
					const apart =
						first.position.x + a.width <= second.position.x ||
						second.position.x + b.width <= first.position.x ||
						first.position.y + a.height <= second.position.y ||
						second.position.y + b.height <= first.position.y;

					expect(apart, `${process.process_id}: ${first.id} and ${second.id}`).toBe(true);
				}
			}
		}
	});

	it('returns new nodes and leaves the ones it was given as they were', () => {
		const { nodes, edges } = processToGraph(processes[0]);
		const before = JSON.stringify(nodes);

		layoutJourneyGraph(nodes, edges);

		expect(JSON.stringify(nodes)).toBe(before);
	});
});
