import { describe, expect, it } from 'vitest';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { hintBracketWidth, hintGap, hintLineLength, hintNodes, hintNoteWidth } from '$lib/hints/hint-nodes';
import { processToGraph } from '$lib/process-graph/process-to-graph';
import type { ProcessNode } from '$lib/process-graph/process-graph-types';

// Three messages in a row, so each is a box of the same kind.
const say = (message: string, next?: string) => ({ state_type: 'output' as const, channel: 'transcript' as const, message, ...(next ? { next } : {}) });
const journey: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'a', vars: {}, states: { a: say('A', 'b'), b: say('B', 'c'), c: say('C') } };
const nodes = processToGraph(journey).nodes.filter((node) => node.data.stateId !== undefined);
const boxWidth = (code: string) => {
	const node = nodes.find((each) => each.data.stateId === code);
	return node?.type === 'step' ? node.data.width : 0;
};

// Places every node at a fixed spot by its state, so where a hint goes can be worked out by hand.
const placeAt = (places: Record<string, { x: number; y: number }>) => (node: ProcessNode) => places[node.data.stateId ?? ''] ?? { x: 0, y: 0 };
const hintWidth = hintBracketWidth + hintLineLength + hintNoteWidth;

describe('hintNodes', () => {
	it('draws a hint to the right of shapes in the right half of the graph, as tall as them', () => {
		const places = placeAt({ a: { x: 0, y: 0 }, b: { x: 500, y: 100 }, c: { x: 500, y: 200 } });
		const [hint] = hintNodes([{ stateIds: ['b', 'c'], title: 'Title', advice: 'Advice' }], nodes, places);

		expect(hint.position).toEqual({ x: 500 + boxWidth('b') + hintGap, y: 100 });
		expect(hint.data).toEqual({ title: 'Title', advice: 'Advice', side: 'right' });
		expect(hint.selectable).toBe(false);
		expect(hint.draggable).toBe(false);
	});

	it('draws a hint to the left of shapes in the left half of the graph', () => {
		const places = placeAt({ a: { x: 0, y: 0 }, b: { x: 500, y: 100 }, c: { x: 500, y: 200 } });
		const [hint] = hintNodes([{ stateIds: ['a'], title: 'Title', advice: 'Advice' }], nodes, places);

		expect(hint.position.x).toBe(-hintGap - hintWidth);
		expect(hint.data.side).toBe('left');
	});

	it('draws no hint about states that are not shown', () => {
		expect(hintNodes([{ stateIds: ['missing'], title: 'Title', advice: 'Advice' }], nodes, placeAt({}))).toEqual([]);
	});
});
