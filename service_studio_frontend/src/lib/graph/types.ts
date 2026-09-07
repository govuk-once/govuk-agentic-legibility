import type { Edge, Node } from '@xyflow/svelte';

// These types describe data shared by the fixture, layout and components so each part uses the same graph structure.
export type StepNodeData = {
	title: string;
	description: string;
	stepId?: string;
	stepNumber?: number;
	appearance?: 'default' | 'editing' | 'bypassed';
};

export type ConditionNodeData = {
	question: string;
};

export type TerminalNodeData = {
	label: string;
	appearance: 'start' | 'end';
};

export type BranchEdgeData = {
	appearance: 'positive' | 'negative';
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
