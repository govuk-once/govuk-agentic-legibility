// These types describe data shared by the graph builder, layout and components so each part uses the same graph structure.

// A plain top left coordinate in canvas pixels, assigned by the layout and read straight into each node's
// CSS position. Kept as its own type so the builder can hand out a placeholder before layout runs.
export type GraphPoint = { x: number; y: number };

export type StepNodeData = {
	title: string;
	description: string;
	stepId?: string;
	stepNumber?: number;
	// Computed from the title, and the title and description together, so each node's box fits its own
	// content, rather than every node sharing one fixed width and height that wastes space for short
	// content and clips long content.
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

// The label and tag colour shown on one branch outcome. The step each one leads to is not named here, it
// is worked out from position, see BranchDecoration below.
export type BranchLabel = {
	label: string;
	tagColour: string;
};

// Describes the one branch point a demo journey can show, entirely by position: the step at afterIndex is
// the one users make the choice at, the two steps immediately after it are the two possible outcomes, and
// the step after those is where they rejoin. Resolving this by position, rather than by fixed step ids,
// is what makes reordering steps also reorder the graph, since whichever steps currently occupy those
// positions play the anchor and outcome roles. This is a deliberate interim simplification standing in
// for a real branching implementation, kept as explicit configuration rather than baked into the graph builder so
// different example journeys can each describe their own branch point without editing that code.
export type BranchDecoration = {
	afterIndex: number;
	question: string;
	branchLabels: [BranchLabel, BranchLabel];
};
