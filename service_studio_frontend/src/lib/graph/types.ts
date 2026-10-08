// These types describe data shared by the graph builder, layout and components so each part uses the same graph structure. Node and edge themselves come from Svelte Flow, this file only says what each of our three node kinds carries as its own data.

import type { Node, Edge } from '@xyflow/svelte';
import type { ServiceStepKind } from '$lib/schema';

export type StepNodeData = {
	title: string;
	stepId?: string;
	stepNumber?: number;
	// How the step is delivered, from the canonical schema, so the list and the node can show a matching
	// tag without either one reaching back into the service definition.
	kind: ServiceStepKind;
	// Computed from the title, so each node's box fits its own title rather than every node sharing one
	// fixed width and height that wastes space for a short title and clips a long one.
	width: number;
	height: number;
	ariaLabel: string;
};

// A gateway diamond carries no routing data of its own, only enough to label it for a screen reader: it
// is a plain shape, the route it stands for is named and edited on the step that owns it, never here.
// draft marks one placed from the toolbar but not yet wired to a step on both ends: it exists only on the
// canvas, not in the service, until connecting it up promotes it into a real gateway. See JourneyGraph.svelte.
export type ConditionNodeData = {
	ariaLabel: string;
	draft?: boolean;
};

export type TerminalNodeData = {
	label: string;
	appearance: 'start' | 'end';
	ariaLabel: string;
	// See ConditionNodeData.draft: a draft start or end is promoted the moment its one connection to a real
	// step is made, reassigning the journey's entry point or clearing that step's routes respectively.
	draft?: boolean;
};

export type StepNode = Node<StepNodeData, 'step'>;
export type ConditionNode = Node<ConditionNodeData, 'condition'>;
export type TerminalNode = Node<TerminalNodeData, 'terminal'>;

export type JourneyNode = StepNode | ConditionNode | TerminalNode;

// The kind separates an ordinary sequence step from a branch outcome, so the two can be told apart
// without either one carrying its own label: a branch route's label and condition live on the step's own
// transition data, edited in the step editor. label here, when set, is a read only copy of that same
// route's label for display on the canvas, never a second place it can be edited from. draft marks a
// connection made to or from a draft node, not yet a real transition, see ConditionNodeData.draft.
export type JourneyEdgeData = { kind: 'sequence' | 'branch'; draft?: boolean };
export type JourneyEdge = Edge<JourneyEdgeData>;

export type JourneyGraphElements = {
	nodes: JourneyNode[];
	edges: JourneyEdge[];
};
