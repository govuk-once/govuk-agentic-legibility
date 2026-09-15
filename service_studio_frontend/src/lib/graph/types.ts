// These types describe data shared by the graph builder, layout and components so each part uses the same graph structure.

import type { ServiceStepKind } from '$lib/schema';

// A plain top left coordinate in canvas pixels, assigned by the layout and read straight into each node's
// CSS position. Kept as its own type so the builder can hand out a placeholder before layout runs.
export type GraphPoint = { x: number; y: number };

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
};

export type ConditionNodeData = {
	question: string;
};

export type TerminalNodeData = {
	label: string;
	appearance: 'start' | 'end';
};

// Every node carries the same shape, differing only by its type tag and data, so the layout can size and
// place them without knowing which component will render each one.
export type StepNode = {
	id: string;
	type: 'step';
	position: GraphPoint;
	data: StepNodeData;
	ariaLabel: string;
};

export type ConditionNode = {
	id: string;
	type: 'condition';
	position: GraphPoint;
	data: ConditionNodeData;
	ariaLabel: string;
};

export type TerminalNode = {
	id: string;
	type: 'terminal';
	position: GraphPoint;
	data: TerminalNodeData;
	ariaLabel: string;
};

export type JourneyNode = StepNode | ConditionNode | TerminalNode;

// A connection between two nodes. The kind separates an ordinary sequence step from a branch outcome, and
// only branch outcomes carry a label and a tag colour. The tag colour reuses the GOV.UK tag colour names
// already used for step tags rather than inventing a second colour system, and it is a colour rather than
// a good or bad flag because a branch is not always a good or bad outcome, it can just as easily be two
// equally valid paths.
export type JourneyEdge = {
	id: string;
	source: string;
	target: string;
	label?: string;
	kind: 'sequence' | 'branch';
	tagColour?: string;
};

export type JourneyGraphElements = {
	nodes: JourneyNode[];
	edges: JourneyEdge[];
};
