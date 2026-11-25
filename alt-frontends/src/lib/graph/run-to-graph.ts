import { estimateStepNodeHeight, estimateStepNodeWidth } from './node-sizing';
import type { FsmState, WorkflowDefinition } from './fsm';
import type { JourneyEdge, JourneyGraphElements, JourneyNode, StepNodeData } from './types';

// node-sizing.ts's height estimate is tuned for StepNode.svelte's single title line; RunStepNode.svelte
// adds a kind-badge row above the title, so its box needs a bit more height than that estimate alone.
const KIND_BADGE_HEIGHT = 18;

/**
 * Finds which process in the definition contains the given state id, falling back to the definition's
 * entry process when no state id is known yet (a run that hasn't reached its first `awaiting` state) or
 * the id can't be found (e.g. a state reached only via a sub-process this scoped-to-one-process renderer
 * doesn't expand).
 */
export function findProcessContaining(
  definition: WorkflowDefinition,
  stateId: string | null | undefined
): string {
  if (stateId) {
    for (const [processId, process] of Object.entries(definition.processes)) {
      if (stateId in process.states) return processId;
    }
  }
  return definition.entry;
}

function titleFor(stateId: string, state: FsmState): string {
  switch (state.type) {
    case 'input':
      return state.prompt || stateId;
    case 'output':
      return state.message || stateId;
    case 'choice':
      return stateId;
    case 'invoke':
      return `Invoke: ${state.process}`;
    case 'call':
      return `Call: ${state.service}.${state.method}`;
    case 'assign':
      return stateId;
    case 'end':
      return state.outcome || state.status || stateId;
    default:
      return stateId;
  }
}

function nextTargets(state: FsmState): Array<{ target: string; kind: 'sequence' | 'branch' }> {
  if (state.type === 'choice') {
    const targets: Array<{ target: string; kind: 'sequence' | 'branch' }> = state.rules.map((rule) => ({
      target: rule.next,
      kind: 'branch'
    }));
    if (state.default) targets.push({ target: state.default, kind: 'branch' });
    return targets;
  }
  if (state.type === 'end') return [];
  return state.next ? [{ target: state.next, kind: 'sequence' }] : [];
}

/**
 * Builds one process's states into a JourneyGraphElements graph: a start terminal wired to the process's
 * start state, one node per state (a plain step node for `invoke`, not an expansion of its sub-process —
 * a full nested-process graph is out of scope for this first cut), a diamond for `choice`, and an end
 * terminal for every `end` state. `currentStateId` (from the run's `awaiting.state_id`) is highlighted as
 * the step the run is on.
 */
export function runToGraph(
  definition: WorkflowDefinition,
  processId: string,
  currentStateId: string | null | undefined
): JourneyGraphElements {
  const process = definition.processes[processId];
  if (!process) return { nodes: [], edges: [] };

  const nodes: JourneyNode[] = [];
  const edges: JourneyEdge[] = [];

  nodes.push({
    id: '__start__',
    type: 'terminal',
    position: { x: 0, y: 0 },
    ariaLabel: 'Start',
    data: { label: 'Start', appearance: 'start' }
  });
  edges.push({
    id: `__start__->${process.start}`,
    source: '__start__',
    target: process.start,
    kind: 'sequence'
  });

  for (const [stateId, state] of Object.entries(process.states)) {
    if (state.type === 'choice') {
      nodes.push({
        id: stateId,
        type: 'condition',
        position: { x: 0, y: 0 },
        ariaLabel: `Condition: ${stateId}`
      });
    } else if (state.type === 'end') {
      const label = state.outcome || state.status || 'End';
      nodes.push({
        id: stateId,
        type: 'terminal',
        position: { x: 0, y: 0 },
        ariaLabel: label,
        data: { label, appearance: 'end' }
      });
    } else {
      const title = titleFor(stateId, state);
      const width = estimateStepNodeWidth(title);
      const height = estimateStepNodeHeight(title, width) + KIND_BADGE_HEIGHT;
      const data: StepNodeData = {
        title,
        kind: state.type,
        status: stateId === currentStateId ? 'current' : 'default',
        width,
        height
      };
      nodes.push({
        id: stateId,
        type: 'step',
        position: { x: 0, y: 0 },
        ariaLabel: `${state.type}: ${title}`,
        data
      });
    }

    for (const { target, kind } of nextTargets(state)) {
      edges.push({ id: `${stateId}->${target}`, source: stateId, target, kind });
    }
  }

  return { nodes, edges };
}
