import type { Node } from '@xyflow/svelte';
import { nodeSize } from '$lib/graph-kit/layout';
import type { ProcessNode } from '$lib/process-graph/process-graph-types';

/*
	The best practice hints drawn on the canvas. Each hint is one node beside the shapes it is about: a bracket down
	their side, a dotted line, and a note with the hint in it. It is drawn on the outer side of the shapes, to the
	right of shapes in the right half of the graph and to the left of shapes in the left half, so the note sits in
	the space beside the journey and not over it. It is worked out from where each shape is now, so it follows a box
	the person has dragged once the drag ends. A hint about states that are not shown, such as ones hidden with the
	developer states, is not drawn.
*/

// A best practice hint to show beside a group of states on the canvas: the states it is about, a short title, and a
// sentence of advice.
export type CanvasHint = { stateIds: string[]; title: string; advice: string };

// The node type the graph draws a hint with.
export const hintNodeType = 'hint';

// The space between the shapes and the bracket, the width of the bracket and the dotted line, and the width of the
// note. The hint node is wide enough for all of them.
export const hintGap = 15;
export const hintBracketWidth = 8;
export const hintLineLength = 15;
export const hintNoteWidth = 260;

// What a hint node carries: the hint's title, its advice, and the side of the shapes it is drawn on.
export type HintNodeData = { title: string; advice: string; side: 'left' | 'right' };

/**
 * Builds one node for each hint that has a shape shown, beside the shapes it is about and as tall as them. A hint
 * cannot be chosen, dragged or joined, so it never gets in the way of the graph.
 */
export function hintNodes(hints: CanvasHint[], nodes: ProcessNode[], positionOf: (node: ProcessNode) => { x: number; y: number }): Node[] {
	const edgesOf = (node: ProcessNode) => {
		const { x, y } = positionOf(node);
		const { width, height } = nodeSize(node);
		return { left: x, top: y, right: x + width, bottom: y + height };
	};

	// The middle of the whole graph from left to right, which decides the side each hint is drawn on.
	const everyEdge = nodes.map(edgesOf);
	const graphMiddle = (Math.min(...everyEdge.map((edge) => edge.left)) + Math.max(...everyEdge.map((edge) => edge.right))) / 2;
	const hintWidth = hintBracketWidth + hintLineLength + hintNoteWidth;

	return hints.flatMap((hint, index): Node[] => {
		const shapes = nodes.filter((node) => node.data.stateId !== undefined && hint.stateIds.includes(node.data.stateId));
		if (shapes.length === 0) return [];

		const edges = shapes.map(edgesOf);
		const left = Math.min(...edges.map((edge) => edge.left));
		const top = Math.min(...edges.map((edge) => edge.top));
		const right = Math.max(...edges.map((edge) => edge.right));
		const bottom = Math.max(...edges.map((edge) => edge.bottom));
		const side = (left + right) / 2 < graphMiddle ? 'left' : 'right';

		return [
			{
				id: `hint:${index}`,
				type: hintNodeType,
				position: { x: side === 'right' ? right + hintGap : left - hintGap - hintWidth, y: top },
				width: hintWidth,
				height: bottom - top,
				data: { title: hint.title, advice: hint.advice, side } satisfies HintNodeData,
				draggable: false,
				selectable: false,
				connectable: false,
				focusable: false,
				// The node's own wrapper would otherwise catch a click or a drag meant for the canvas or a box.
				style: 'pointer-events: none'
			}
		];
	});
}
