import dagre from '@dagrejs/dagre';
import type { ProcessNode } from './process-graph-types';
import type { JourneyNode } from './types';

// The layout reads only the type, the id and the step size of a node, and only the two ends of an edge.
// The original graph and the process graph both have the same three node kinds with those fields, so one
// layout serves both and is not copied. The original graph is removed when the editor is replaced.
type LayoutNode = JourneyNode | ProcessNode;
type LayoutEdge = { source: string; target: string };

// Condition and terminal nodes keep fixed dimensions, but a step's width and height are worked out per
// node from its own title (see node-sizing.ts), rather than every step sharing one fixed size that
// wastes space for a short title and clips a long one. These sizes match the shapes drawn in
// ConditionNode.svelte and TerminalNode.svelte, since edges anchor to these dimensions: a 40px diamond
// for a decision, a 40px circle for a start or end.
const conditionAndTerminalDimensions = {
	condition: { width: 40, height: 40 },
	terminal: { width: 40, height: 40 }
} as const;

// Horizontal gap between two nodes sharing a rank, vertical gap between one rank and the next, and the
// blank border kept around the whole graph. Tuned so branches stay legible in the narrow graph column.
const NODE_GAP = 50;
const RANK_GAP = 60;
const MARGIN = 30;

// The dagre settings that change how a graph is arranged. Both are optional, and leaving them out keeps
// dagre's own defaults, which is how the original graph is laid out.
export type LayoutOptions = {
	// Which corner of a group of connected boxes the others line up with. A straight run of boxes then
	// stays in one column instead of drifting sideways.
	align?: 'UL' | 'UR' | 'DL' | 'DR';
	// How boxes are put into rows. See the dagre documentation for what each one favours.
	ranker?: 'network-simplex' | 'tight-tree' | 'longest-path';
};

// The settings used for the process graph. The tight tree ranker keeps each box close to the box it
// follows, which measured about 17 percent less sideways drift on the real example processes than
// dagre's default and made no graph wider. The original graph keeps dagre's defaults.
export const processLayoutOptions: LayoutOptions = { ranker: 'tight-tree' };

/**
 * Returns the width and height this node occupies, so a step's dynamic dimensions and every other node's
 * fixed dimensions are looked up the same way. Exported because the graph component reuses it to work out
 * where each edge should meet a node.
 */
export function nodeSize(node: LayoutNode): { width: number; height: number } {
	if (node.type === 'step') {
		return { width: node.data.width, height: node.data.height };
	}
	return conditionAndTerminalDimensions[node.type];
}

/**
 * Positions a graph from top to bottom, handing the hard part, ranking, ordering ranks to minimise edge
 * crossings, and breaking any cycle so a journey that loops back on itself still lays out, over to dagre.
 * That is a well tested implementation of the same problem our own node and edge shapes describe, rather
 * than one this project would otherwise have to write and maintain from scratch. Dagre has no dependency
 * on rendering or dragging, it only computes positions, so this stays a pure function: it builds a fresh
 * graph from its arguments on every call and never mutates the nodes or edges it is given.
 */
export function layoutJourneyGraph<Node extends LayoutNode>(
	nodes: Node[],
	edges: LayoutEdge[],
	options: LayoutOptions = {}
): { nodes: Node[]; width: number; height: number } {
	const graph = new dagre.graphlib.Graph();
	// Dagre requires an edge label factory even though the graph does not attach layout metadata to connections.
	graph.setDefaultEdgeLabel(() => ({}));
	graph.setGraph({ rankdir: 'TB', nodesep: NODE_GAP, ranksep: RANK_GAP, marginx: MARGIN, marginy: MARGIN, ...options });

	for (const node of nodes) {
		// Spread into a fresh object for every node, including nodes of the same type that would otherwise
		// share the one constant object from conditionAndTerminalDimensions, because dagre adds the
		// computed position directly onto the object it is given, and two nodes sharing that object would
		// end up with the same position.
		graph.setNode(node.id, { ...nodeSize(node) });
	}

	for (const edge of edges) {
		graph.setEdge(edge.source, edge.target);
	}

	// Run layout after every node and connection is registered, since dagre ranks and orders the complete
	// graph in one pass rather than incrementally.
	dagre.layout(graph);

	const positionedNodes = nodes.map((node) => {
		const { width, height } = nodeSize(node);
		const centre = graph.node(node.id);

		// Convert dagre's centre coordinates to the top left coordinates Svelte Flow positions nodes by.
		// width/height are set here too, alongside data.width/height, since Svelte Flow uses the node's own
		// top level fields for handle placement and the connection line, not the data object's copy.
		return {
			...node,
			position: { x: centre.x - width / 2, y: centre.y - height / 2 },
			width,
			height
		};
	});

	// Dagre decides the order of the boxes in each row so that the fewest lines cross, and that order is kept.
	// The two passes below only slide boxes sideways within their row to sit under the box they follow.
	centreBranchesUnderParents(positionedNodes, edges);
	centreEndDotsUnderParents(positionedNodes, edges);

	const graphSize = graph.graph();

	return {
		nodes: positionedNodes,
		width: graphSize.width ?? 0,
		height: graphSize.height ?? 0
	};
}

/**
 * For every node with more than one outgoing edge, such as a decision, moves the boxes it leads to as a
 * group so they sit evenly to its left and right and not far to one side. The order of the boxes is the
 * order dagre chose, because dagre picks the order that crosses the fewest lines, and putting them back in
 * step order would make the lines below them cross. A group is only moved when the boxes it would pass over
 * or land beside on the same row leave a gap, so it never crowds another box. Mutates the positioned nodes
 * in place, since it only ever moves a node sideways within its own row.
 */
function centreBranchesUnderParents<Node extends LayoutNode>(positionedNodes: Node[], edges: LayoutEdge[]): void {
	const nodeById = new Map(positionedNodes.map((node) => [node.id, node]));

	// A set is used because two routes can lead to the same target, such as an error route and a normal
	// route to one end state, and a node must only be moved once.
	const childrenBySource = new Map<string, Set<string>>();
	for (const edge of edges) {
		const targets = childrenBySource.get(edge.source);
		if (targets) {
			targets.add(edge.target);
		} else {
			childrenBySource.set(edge.source, new Set([edge.target]));
		}
	}

	// Nodes on the same row share a centre line, so comparing centres works even when their heights differ.
	const centreY = (node: Node) => node.position.y + nodeSize(node).height / 2;

	for (const [sourceId, childIds] of childrenBySource) {
		const source = nodeById.get(sourceId);
		const children = [...childIds].map((id) => nodeById.get(id)).filter((node): node is Node => !!node);
		if (!source || children.length < 2) continue;

		// Only moves boxes dagre already placed on the same row: anything else sharing one source but landing
		// elsewhere is left exactly where dagre put it.
		const rowCentre = centreY(children[0]);
		if (!children.every((child) => Math.abs(centreY(child) - rowCentre) < 0.5)) continue;

		const left = Math.min(...children.map((child) => child.position.x));
		const right = Math.max(...children.map((child) => child.position.x + nodeSize(child).width));
		const shift = source.position.x + nodeSize(source).width / 2 - (left + right) / 2;

		// The whole stretch the group covers, from where it is to where it would be, with a gap each side. Any
		// other box of the row inside it would be crowded or jumped over, which changes the order of the row.
		const from = Math.min(left, left + shift) - NODE_GAP;
		const to = Math.max(right, right + shift) + NODE_GAP;
		const crowded = positionedNodes.some(
			(other) =>
				!childIds.has(other.id) &&
				Math.abs(centreY(other) - rowCentre) < 0.5 &&
				other.position.x < to &&
				other.position.x + nodeSize(other).width > from
		);
		if (!crowded) {
			for (const child of children) child.position = { ...child.position, x: child.position.x + shift };
		}
	}
}

/**
 * Puts each end dot directly under the step that leads to it. Dagre places a dot as it suits the rest of
 * the graph, which can leave it to one side or far below and make it look as though it belongs to a
 * neighbouring step. Nothing leaves an end dot, so moving it cannot disturb any other line. The dot is
 * tried first just below its step, then at the depth dagre gave it. It is only moved to a place that is
 * clear, both for the dot itself and for the line down to it, so it never lands on top of a box or hides a
 * line behind one. Mutates the positioned nodes in place.
 */
function centreEndDotsUnderParents<Node extends LayoutNode>(positionedNodes: Node[], edges: LayoutEdge[]): void {
	const nodeById = new Map(positionedNodes.map((node) => [node.id, node]));

	for (const dot of positionedNodes) {
		if (dot.type !== 'terminal' || dot.data.appearance !== 'end') continue;

		// Only a dot with exactly one line into it has a single step to sit under.
		const into = edges.filter((edge) => edge.target === dot.id);
		const parent = into.length === 1 ? nodeById.get(into[0].source) : undefined;
		if (!parent) continue;

		const { width, height } = nodeSize(dot);
		const left = parent.position.x + nodeSize(parent).width / 2 - width / 2;
		const parentBottom = parent.position.y + nodeSize(parent).height;

		// Whether any other box is in the columns of the dot, between the bottom of the step and the bottom
		// of a dot placed at the given height. That covers the dot and the line down to it.
		const isClear = (top: number) =>
			!positionedNodes.some(
				(other) =>
					other !== dot &&
					other !== parent &&
					other.position.x < left + width + NODE_GAP / 2 &&
					other.position.x + nodeSize(other).width > left - NODE_GAP / 2 &&
					other.position.y < top + height &&
					other.position.y + nodeSize(other).height > parentBottom
			);

		const justBelow = parentBottom + RANK_GAP;
		const place = [justBelow, dot.position.y].find((top) => top >= justBelow - 0.5 && isClear(top));
		if (place !== undefined) dot.position = { x: left, y: place };
	}
}
