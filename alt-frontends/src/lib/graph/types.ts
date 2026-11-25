// Shape mirrors service_studio_frontend's graph module (ConditionNode/TerminalNode/
// GraphMinimap/layout.ts are ported verbatim from there) so those files need no
// internal changes. `StepNodeData` replaces that project's `ServiceStepKind` coupling
// with the run-specific fields RunStepNode.svelte and run-to-graph.ts need instead.

export interface GraphPoint {
  x: number;
  y: number;
}

export type RunStepStatus = 'default' | 'current';

export interface StepNodeData {
  title: string;
  kind: string;
  status: RunStepStatus;
  width: number;
  height: number;
}

export interface TerminalNodeData {
  label: string;
  appearance: 'start' | 'end';
}

export interface StepNode {
  id: string;
  type: 'step';
  position: GraphPoint;
  ariaLabel: string;
  data: StepNodeData;
}

export interface ConditionNode {
  id: string;
  type: 'condition';
  position: GraphPoint;
  ariaLabel: string;
}

export interface TerminalNode {
  id: string;
  type: 'terminal';
  position: GraphPoint;
  ariaLabel: string;
  data: TerminalNodeData;
}

export type JourneyNode = StepNode | ConditionNode | TerminalNode;

export interface JourneyEdge {
  id: string;
  source: string;
  target: string;
  kind: 'sequence' | 'branch';
}

export interface JourneyGraphElements {
  nodes: JourneyNode[];
  edges: JourneyEdge[];
}
