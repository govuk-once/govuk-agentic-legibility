// These types describe the nodes and edges built from one process, shared by the graph builder, the layout and the components. Node and Edge come from Svelte Flow, so this file only says what each kind of node carries as its own data. The three node kinds match the existing graph, so the same components can draw them.

import type { Edge, Node } from '@xyflow/svelte';
import type { State } from '$lib/schema/workflow/process';
import type { Route } from '$lib/schema/workflow/routes';
import type { CompletionStatus } from '$lib/schema/workflow/states';

// A box for any state that is neither a decision nor an end. The state type is the schema's own name
// for it, such as input or call, so a label for the person can be chosen later without changing this.
export type ProcessStepNodeData = {
	stateId: string;
	stepNumber: number;
	title: string;
	stateType: State['type'];
	// Set only on an invoke state. It names the process the state runs, so the box can offer to open it.
	opensProcess?: { id: string; title: string };
	// Worked out from the title, so each box fits its own title instead of sharing one fixed size.
	width: number;
	height: number;
	ariaLabel: string;
};

// The diamond for a choice state. Its title is only for a screen reader, the routes are on the edges.
export type ProcessDecisionNodeData = {
	stateId: string;
	title: string;
	ariaLabel: string;
	// Marks a shape placed from the toolbar that is not yet joined to a state. The node components
	// already draw it dashed, and nothing sets it until the editing commits.
	draft?: boolean;
};

// The dot for the start of the journey or for an end state. An end dot also carries the status of the
// end state, so it can be coloured by how the journey finished.
export type ProcessTerminalNodeData = {
	label: 'Start' | 'End';
	appearance: 'start' | 'end';
	ariaLabel: string;
	stateId?: string;
	// The title of an end state, used by the list of states. The start dot has none.
	title?: string;
	status?: CompletionStatus;
	// See ProcessDecisionNodeData.
	draft?: boolean;
};

export type ProcessStepNode = Node<ProcessStepNodeData, 'step'>;
export type ProcessDecisionNode = Node<ProcessDecisionNodeData, 'condition'>;
export type ProcessTerminalNode = Node<ProcessTerminalNodeData, 'terminal'>;

export type ProcessNode = ProcessStepNode | ProcessDecisionNode | ProcessTerminalNode;

// The kind of an edge is the kind of route it was built from, plus start for the edge that leaves the
// start dot. Keeping them apart lets a timeout or an error route be drawn differently from a normal one.
export type ProcessEdgeData = { kind: Route['kind'] | 'start' };
export type ProcessEdge = Edge<ProcessEdgeData>;

export type ProcessGraphElements = {
	nodes: ProcessNode[];
	edges: ProcessEdge[];
};
