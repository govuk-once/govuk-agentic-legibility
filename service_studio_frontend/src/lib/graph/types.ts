import type { Edge, Node } from '@xyflow/svelte';

// These types describe data shared by the graph builder, layout and components so each part uses the same graph structure.
export type StepNodeData = {
	title: string;
	description: string;
	stepId?: string;
	stepNumber?: number;
	// Bypassed marks a synthetic branch outcome that has no step of its own. Selection alone is what shows
	// a step is being edited, so there is no separate editing appearance to track here.
	appearance?: 'bypassed';
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

// A tag colour rather than a positive or negative flag, because a branch is not always a good or bad
// outcome, it can just as easily be two equally valid paths, and this reuses the same GOV.UK tag colour
// names already used for step tags rather than inventing a second colour system.
export type BranchEdgeData = {
	tagColour: string;
};

export type StepNode = Node<StepNodeData, 'step'>;
export type ConditionNode = Node<ConditionNodeData, 'condition'>;
export type TerminalNode = Node<TerminalNodeData, 'terminal'>;
export type BranchEdge = Edge<BranchEdgeData, 'branch'>;
export type JourneyNode = StepNode | ConditionNode | TerminalNode;
export type JourneyEdge = Edge | BranchEdge;

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
