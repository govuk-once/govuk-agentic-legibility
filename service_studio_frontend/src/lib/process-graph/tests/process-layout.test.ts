import { describe, expect, it } from 'vitest';
import { serviceExamples } from '$lib/examples/services';
import { NODE_GAP, nodeSize, RANK_GAP } from '$lib/graph-kit/layout';
import type { Process } from '$lib/schema/workflow/process';
import { arrangeProcessGraph, placeBesideNeighbours } from '$lib/process-graph/arrange';
import { processToGraph, separateEndDots, visibleGraph } from '$lib/process-graph/process-to-graph';

const processes = serviceExamples.flatMap((example) => Object.values(example.workflow?.processes ?? {}));

describe('arrangeProcessGraph with process graphs', () => {
	it('gives every node of every real process a position', () => {
		for (const process of processes) {
			const { nodes, edges } = processToGraph(process);
			const laidOut = arrangeProcessGraph(nodes, edges);

			expect(laidOut.nodes, process.process_id).toHaveLength(nodes.length);
			for (const node of laidOut.nodes) {
				expect(Number.isFinite(node.position.x), `${process.process_id} ${node.id}`).toBe(true);
				expect(Number.isFinite(node.position.y), `${process.process_id} ${node.id}`).toBe(true);
			}
		}
	});

	it('keeps the nodes of every real process from overlapping, with error routes on or off', () => {
		for (const process of processes) {
			for (const showErrorRoutes of [true, false]) {
				const shown = separateEndDots(visibleGraph(processToGraph(process), { showErrorRoutes }));
				const { nodes: laidOut } = arrangeProcessGraph(shown.nodes, shown.edges);

				for (const [index, first] of laidOut.entries()) {
					for (const second of laidOut.slice(index + 1)) {
						const a = nodeSize(first);
						const b = nodeSize(second);
						const apart =
							first.position.x + a.width <= second.position.x ||
							second.position.x + b.width <= first.position.x ||
							first.position.y + a.height <= second.position.y ||
							second.position.y + b.height <= first.position.y;

						expect(apart, `${process.process_id} ${showErrorRoutes}: ${first.id} and ${second.id}`).toBe(true);
					}
				}
			}
		}
	});

	it('returns new nodes and leaves the ones it was given as they were', () => {
		const { nodes, edges } = processToGraph(processes[0]);
		const before = JSON.stringify(nodes);

		arrangeProcessGraph(nodes, edges);

		expect(JSON.stringify(nodes)).toBe(before);
	});
});

describe('the layout of the shown graph', () => {
	// The distance between the centre of a box and the centre of the box a line leads to. A line that runs
	// straight down is 0, and a long one is a sign that a box was pushed far to the side.
	function sidewaysDistances(showErrorRoutes: boolean): number[] {
		return processes.flatMap((process) => {
			const shown = separateEndDots(visibleGraph(processToGraph(process), { showErrorRoutes }));
			const laidOut = arrangeProcessGraph(shown.nodes, shown.edges).nodes;
			const centres = new Map(laidOut.map((node) => [node.id, node.position.x + nodeSize(node).width / 2]));

			return shown.edges.map((edge) => Math.abs(centres.get(edge.source)! - centres.get(edge.target)!));
		});
	}

	it('keeps the lines of the real processes close to straight down on average', () => {
		const distances = sidewaysDistances(false);
		const average = distances.reduce((total, distance) => total + distance, 0) / distances.length;

		// Measured at 107 when this was written. The limit leaves a little room, but a layout change that
		// makes the lines drift more than this should be looked at.
		expect(average).toBeLessThan(130);
	});

	it('keeps the branches of a decision close to it when they share a row', () => {
		const distances = processes.flatMap((process) => {
			const shown = separateEndDots(visibleGraph(processToGraph(process), { showErrorRoutes: false }));
			const laidOut = arrangeProcessGraph(shown.nodes, shown.edges).nodes;
			const byId = new Map(laidOut.map((node) => [node.id, node]));
			const centreX = (id: string) => byId.get(id)!.position.x + nodeSize(byId.get(id)!).width / 2;
			const centreY = (id: string) => byId.get(id)!.position.y + nodeSize(byId.get(id)!).height / 2;

			return shown.nodes.flatMap((node) => {
				if (node.type !== 'condition') return [];
				const branches = shown.edges.filter((edge) => edge.source === node.id).map((edge) => edge.target);
				const onOneRow = branches.length > 1 && branches.every((branch) => Math.abs(centreY(branch) - centreY(branches[0])) < 1);
				return onOneRow ? branches.map((branch) => Math.abs(centreX(branch) - centreX(node.id))) : [];
			});
		});
		const average = distances.reduce((total, distance) => total + distance, 0) / distances.length;

		// Measured at 204 when this was written, down from 235 before the branches were centred.
		expect(distances.length).toBeGreaterThan(0);
		expect(average).toBeLessThan(220);
	});

	it('puts most end dots directly under the step that leads to them', () => {
		const offsets = processes.flatMap((process) => {
			const shown = separateEndDots(visibleGraph(processToGraph(process), { showErrorRoutes: false }));
			const laidOut = arrangeProcessGraph(shown.nodes, shown.edges).nodes;
			const byId = new Map(laidOut.map((node) => [node.id, node]));
			const centreX = (id: string) => byId.get(id)!.position.x + nodeSize(byId.get(id)!).width / 2;

			return shown.edges
				.filter((edge) => {
					const target = byId.get(edge.target)!;
					return target.type === 'terminal' && target.data.appearance === 'end';
				})
				.map((edge) => Math.abs(centreX(edge.source) - centreX(edge.target)));
		});
		const directlyUnder = offsets.filter((offset) => offset < 1).length;

		// Measured at 31 of 46 when this was written. The rest sit beside a sibling branch of the same
		// decision, so they cannot be directly under it.
		expect(offsets.length).toBe(46);
		expect(directlyUnder).toBeGreaterThanOrEqual(28);
	});

	// Whether two lines drawn straight from the centre of one box to the centre of another cross each other.
	// Lines that meet at a box do not count. The real lines are curved, but this is close enough to compare layouts.
	function countCrossings(process: (typeof processes)[number]): number {
		const shown = separateEndDots(visibleGraph(processToGraph(process), { showErrorRoutes: false }));
		const laidOut = arrangeProcessGraph(shown.nodes, shown.edges).nodes;
		const centres = new Map(
			laidOut.map((node) => [node.id, { x: node.position.x + nodeSize(node).width / 2, y: node.position.y + nodeSize(node).height / 2 }])
		);
		type Point = { x: number; y: number };
		const side = (a: Point, b: Point, c: Point) => (c.y - a.y) * (b.x - a.x) - (b.y - a.y) * (c.x - a.x);
		let crossings = 0;

		for (const [index, first] of shown.edges.entries()) {
			for (const second of shown.edges.slice(index + 1)) {
				if (new Set([first.source, first.target, second.source, second.target]).size < 4) continue;
				const [a, b] = [centres.get(first.source)!, centres.get(first.target)!];
				const [c, d] = [centres.get(second.source)!, centres.get(second.target)!];
				if (side(a, c, d) * side(b, c, d) < 0 && side(a, b, c) * side(a, b, d) < 0) crossings += 1;
			}
		}
		return crossings;
	}

	it('keeps the number of crossing lines low, and none in the select address process', () => {
		const total = processes.reduce((sum, process) => sum + countCrossings(process), 0);
		const selectAddress = processes.find((process) => process.process_id === 'select_address')!;

		// Measured at 10 across the 14 real processes when this was written, down from 41 when branches
		// were put back in step order. That reordering made the lines below them cross.
		expect(total).toBeLessThanOrEqual(12);
		expect(countCrossings(selectAddress)).toBe(0);
	});

	it('is narrower without the error routes than with them for the entry process of change of address', () => {
		const entry = serviceExamples.find((example) => example.slug === 'change_of_address')!.workflow!;
		const graph = processToGraph(entry.processes[entry.manifest.entry]);
		const withoutErrorRoutes = visibleGraph(graph, { showErrorRoutes: false });

		const narrow = arrangeProcessGraph(withoutErrorRoutes.nodes, withoutErrorRoutes.edges).width;
		const wide = arrangeProcessGraph(graph.nodes, graph.edges).width;

		expect(narrow).toBeLessThan(wide);
	});
});

describe('placeBesideNeighbours', () => {
	// A question, a decision after it and two ends, as the graph draws them.
	const process = {
		process_id: 'p',
		version: '0.1.0',
		vars: {},
		start: 'ask',
		states: {
			ask: { state_type: 'input', prompt: 'Q?', schema: { kind: 'boolean' }, assign: 'ok', next: 'decide' },
			decide: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'ok' }, next: 'yes' }], default: 'no' },
			yes: { state_type: 'end', status: 'success' },
			no: { state_type: 'end', status: 'cancelled' }
		}
	} as unknown as Process;
	const { nodes, edges } = processToGraph(process);
	const ask = nodes.find((node) => node.id === 'ask')!;

	it('places a new box one row below the box that leads into it, and a little to the right', () => {
		const known = new Map([['ask', { x: 100, y: 200 }]]);
		const placed = placeBesideNeighbours(nodes, edges, (id) => known.get(id));
		expect(placed.get('decide')).toEqual({ x: 160, y: 200 + nodeSize(ask).height + RANK_GAP });
	});

	it('places new boxes one after another, so a box can sit beside another new box', () => {
		const known = new Map([['ask', { x: 100, y: 200 }]]);
		const placed = placeBesideNeighbours(nodes, edges, (id) => known.get(id));
		const decide = placed.get('decide')!;
		expect(placed.get('yes')?.y).toBeGreaterThan(decide.y);
		expect(placed.get('no')?.y).toBeGreaterThan(decide.y);
	});

	it('places a box that nothing placed leads into above the box it leads to', () => {
		const known = new Map([['decide', { x: 100, y: 400 }]]);
		const placed = placeBesideNeighbours(nodes, edges, (id) => known.get(id));
		expect(placed.get('ask')!.y).toBeLessThan(400);
	});

	it('slides a new box to the right until it is clear of a box already in that place', () => {
		const below = 200 + nodeSize(ask).height + RANK_GAP;
		const known = new Map([['ask', { x: 100, y: 200 }], ['yes', { x: 150, y: below }]]);
		const placed = placeBesideNeighbours(nodes, edges, (id) => known.get(id));
		const yes = nodes.find((node) => node.id === 'yes')!;
		expect(placed.get('decide')).toEqual({ x: 150 + nodeSize(yes).width + NODE_GAP, y: below });
	});

	it('leaves alone a box that already has a place, and one joined to nothing with a place', () => {
		const known = new Map([['ask', { x: 0, y: 0 }]]);
		const placed = placeBesideNeighbours(nodes, edges, (id) => known.get(id));
		expect(placed.has('ask')).toBe(false);
		expect(placeBesideNeighbours(nodes, edges, () => undefined).size).toBe(0);
	});
});
