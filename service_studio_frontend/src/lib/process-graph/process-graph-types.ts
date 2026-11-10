// These types describe the nodes and edges built from one process, shared by the graph builder, the layout and the components. Node and Edge come from Svelte Flow, so this file only says what each kind of node carries as its own data. Each kind adds the state it stands for to the data that the shared box, diamond and dot shapes need.

import type { Edge, Node } from '@xyflow/svelte';
import type { DecisionNodeData, StepNodeData, TerminalNodeData } from '$lib/graph-kit/node-types';
import type { State } from '$lib/schema/workflow/process';
import type { Route } from '$lib/schema/workflow/routes';
import type { CompletionStatus } from '$lib/schema/workflow/states';

// A box for any state that is neither a decision nor an end. The state type is the schema's own name
// for it, such as input or api_call, so a label for the person can be chosen later without changing this.
export type ProcessStepNodeData = StepNodeData & {
	stateId: string;
	stateType: State['state_type'];
	// Set on a box for a developer state. It takes no step number, and an editor can hide it from the graph.
	developer?: boolean;
};

// The diamond for a choice state. Its title is only for a screen reader, the routes are on the edges.
export type ProcessDecisionNodeData = DecisionNodeData & {
	stateId: string;
	title: string;
};

// The dot for the start of the journey or for an end state. An end dot also carries the status of the
// end state, so it can be coloured by how the journey finished.
export type ProcessTerminalNodeData = TerminalNodeData & {
	label: 'Start' | 'End';
	stateId?: string;
	// The title of an end state, used by the list of states. The start dot has none.
	title?: string;
	status?: CompletionStatus;
};

export type ProcessStepNode = Node<ProcessStepNodeData, 'step'>;
export type ProcessDecisionNode = Node<ProcessDecisionNodeData, 'condition'>;
export type ProcessTerminalNode = Node<ProcessTerminalNodeData, 'terminal'>;

export type ProcessNode = ProcessStepNode | ProcessDecisionNode | ProcessTerminalNode;

// The kind of an edge is the kind of route it was built from, plus start for the edge that leaves the
// start dot. Keeping them apart lets a timeout or an error route be drawn differently from a normal one. The
// path says where the route sits in the state it leaves, so a line chosen on the canvas can be found in the
// process. A draft line is drawn to or from a shape that is not in the process yet.
export type ProcessEdgeData = { kind: Route['kind'] | 'start'; path?: Route['path']; draft?: boolean };
export type ProcessEdge = Edge<ProcessEdgeData>;

// Where the person has dragged boxes to, by node id. A box that is not here stays where the layout put it.
// These positions only describe how the graph is drawn, so they are not part of the workflow and are not saved.
export type NodePositions = Record<string, { x: number; y: number }>;

export type ProcessGraphElements = {
	nodes: ProcessNode[];
	edges: ProcessEdge[];
};

// What a press of the Delete key removed from the canvas. A line between states carries the state it leaves,
// where in that state the route sits, and the state it leads to.
export type DeletedElements = {
	draftIds: string[];
	draftLineIds: string[];
	stateCodes: string[];
	lines: Array<{ source: string; path: (string | number)[]; target: string }>;
};
