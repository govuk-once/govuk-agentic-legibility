import type { Node } from '@xyflow/svelte';
import { nodeSize } from '$lib/graph-kit/layout';
import { moduleTileFor } from '$lib/modules/module-catalogue';
import type { ProcessNode } from './process-graph-types';

/*
	The borders drawn round the states of each copy of a module, so a person can see which boxes came in together.

	1. A border is drawn for each group id, round every box, diamond and dot of that copy that is shown, with the
	   name of the module on its top edge. A state that is hidden, such as an assign or an end only an error route
	   leads to, does not stretch it.
	2. A module of one state has a border as well, so every module on the canvas is named the same way.
	3. The border is worked out from where each shape is now, so it follows a box the person has dragged once the
	   drag ends.
*/

// The space left between the border and the shapes inside it. It leaves room for the name on the top edge.
const borderPadding = 20;

// The node type the graph draws a border with.
export const moduleBorderNodeType = 'moduleBorder';

/**
 * Builds one border node for each copy of a module that has a shape shown, named with the module's label. Each
 * border is drawn behind the shapes and cannot be chosen, moved or joined, so it never gets in the way of the
 * shapes inside it.
 */
export function moduleBorders(nodes: ProcessNode[], positionOf: (node: ProcessNode) => { x: number; y: number }): Node[] {
	const groups = new Map<string, { key: string; left: number; top: number; right: number; bottom: number }>();

	for (const node of nodes) {
		const group = node.data.moduleGroup;
		if (!group) continue;
		const { x, y } = positionOf(node);
		const { width, height } = nodeSize(node);
		const found = groups.get(group.id);
		groups.set(group.id, {
			key: group.key,
			left: Math.min(found?.left ?? x, x),
			top: Math.min(found?.top ?? y, y),
			right: Math.max(found?.right ?? x + width, x + width),
			bottom: Math.max(found?.bottom ?? y + height, y + height)
		});
	}

	return [...groups].map(([id, bounds]): Node => ({
		id: `module-border:${id}`,
		type: moduleBorderNodeType,
		position: { x: bounds.left - borderPadding, y: bounds.top - borderPadding },
		width: bounds.right - bounds.left + borderPadding * 2,
		height: bounds.bottom - bounds.top + borderPadding * 2,
		data: { label: moduleTileFor(bounds.key)?.label ?? bounds.key },
		draggable: false,
		selectable: false,
		connectable: false,
		focusable: false,
		zIndex: -1,
		// The node's own wrapper would otherwise catch a click or a drag meant for the canvas or a box.
		style: 'pointer-events: none'
	}));
}
