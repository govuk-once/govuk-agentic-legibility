import dagre from '@dagrejs/dagre';
import type { JourneyEdge, JourneyNode } from './types';

// Condition and terminal nodes keep fixed dimensions, but a step's width and height are worked out per
// node from its title rather than every step sharing one fixed size that either wastes space for a short
// title or clips a long one. These sizes match ConditionNode.svelte and TerminalNode.svelte, so edges
// anchor to the shape actually rendered: a 40px diamond for a decision, a 40px circle for a start or end.
const conditionAndTerminalDimensions = {
  condition: { width: 40, height: 40 },
  terminal: { width: 40, height: 40 }
} as const;

// Horizontal gap between two nodes on the same rank, vertical gap between ranks, so branches stay legible.
const NODE_GAP = 50;
const RANK_GAP = 60;
const MARGIN = 30;

/**
 * Returns the width and height this node occupies on the canvas: dynamic for a step, the fixed
 * dimensions above for anything else.
 */
export function nodeSize(node: JourneyNode): { width: number; height: number } {
  if (node.type === 'step') return { width: node.data.width, height: node.data.height };
  return conditionAndTerminalDimensions[node.type];
}

/**
 * Lays out a graph from top to bottom, handing the hard part — ranking nodes and ordering them within a
 * rank to minimise edge crossings — to dagre. Dagre has no dependency on rendering or dragging, it only
 * computes positions, so this stays a pure function: it builds a fresh graph from its arguments on every
 * call and never mutates the nodes or edges it is given.
 */
export function layoutJourneyGraph(
  nodes: JourneyNode[],
  edges: JourneyEdge[]
): { nodes: JourneyNode[]; width: number; height: number } {
  const graph = new dagre.graphlib.Graph();

  // Dagre requires an edge label factory even though this graph does not attach any layout metadata to
  // its connections.
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: 'TB', nodesep: NODE_GAP, ranksep: RANK_GAP, marginx: MARGIN, marginy: MARGIN });

  for (const node of nodes) {
    // Spread into a fresh object for every node, including nodes of the same type that would otherwise
    // share the one constant object from conditionAndTerminalDimensions, because dagre adds the computed
    // position directly onto the object it is given, and two nodes sharing that object would end up with
    // the same position.
    graph.setNode(node.id, { ...nodeSize(node) });
  }

  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target);
  }

  // Run layout after every node and connection is registered, so dagre ranks and orders the complete
  // graph in one pass rather than incrementally.
  dagre.layout(graph);

  const positionedNodes = nodes.map((node) => {
    const { width, height } = nodeSize(node);
    const centre = graph.node(node.id);

    // Dagre positions a node by its centre; the rest of this module works in top-left coordinates.
    return {
      ...node,
      position: { x: centre.x - width / 2, y: centre.y - height / 2 }
    };
  }) as JourneyNode[];

  // Dagre only ranks and orders nodes to minimise edge crossings — it has no notion of which branch
  // "comes first" for a gateway's own routes, so this reassigns the same set of x positions dagre already
  // chose, but in step order.
  reorderBranchSiblings(positionedNodes, edges);

  const graphSize = graph.graph();

  return {
    nodes: positionedNodes,
    width: graphSize.width ?? 0,
    height: graphSize.height ?? 0
  };
}

/**
 * For every node with more than one outgoing edge (a gateway's branch routes), sorts those targets into
 * the same order they appear in the input, then hands out dagre's own x positions for that rank to them
 * in that order. Mutates the positioned nodes in place, since it only ever reassigns an x each node
 * already has from dagre, never its rank or the set of positions available within it.
 */
function reorderBranchSiblings(positionedNodes: JourneyNode[], edges: JourneyEdge[]): void {
  const orderIndex = new Map(positionedNodes.map((node, index) => [node.id, index]));
  const nodeById = new Map(positionedNodes.map((node) => [node.id, node]));

  const childrenBySource = new Map<string, string[]>();
  for (const edge of edges) {
    const list = childrenBySource.get(edge.source);
    if (list) {
      list.push(edge.target);
    } else {
      childrenBySource.set(edge.source, [edge.target]);
    }
  }

  for (const childIds of childrenBySource.values()) {
    if (childIds.length < 2) continue;
    const children = childIds.map((id) => nodeById.get(id)).filter((node): node is JourneyNode => !!node);
    if (children.length < 2) continue;

    // Only ever reassigns positions among nodes dagre already placed on the same rank: anything else
    // sharing one source but landing elsewhere, which does not happen for a gateway's own routes but
    // could for a step with an unrelated pair of edges, is left exactly where dagre put it.
    const rankY = children[0].position.y;
    if (!children.every((child) => Math.abs(child.position.y - rankY) < 0.5)) continue;

    const slots = children.map((child) => child.position.x).sort((a, b) => a - b);
    const inStepOrder = [...children].sort(
      (a, b) => (orderIndex.get(a.id) ?? 0) - (orderIndex.get(b.id) ?? 0)
    );

    inStepOrder.forEach((child, index) => {
      child.position = { ...child.position, x: slots[index] };
    });
  }
}
