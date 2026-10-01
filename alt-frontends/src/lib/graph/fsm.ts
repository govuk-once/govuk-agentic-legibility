// Mirrors the FSM definition shape returned by `agent/tools.py:get_workflow_definition()`
// (fetched straight from the workflow server, e.g. dwp_ma1_schema.json) — not a JSON-Schema, and not the
// lighter WorkflowSummary the workflow picker uses.

export interface ChoiceRule {
  when: unknown;
  next: string;
}

export interface FsmInputState {
  type: 'input';
  prompt: string;
  schema: Record<string, unknown>;
  assign?: string;
  next: string;
}

export interface FsmOutputState {
  type: 'output';
  message: string;
  next: string;
}

export interface FsmChoiceState {
  type: 'choice';
  rules: ChoiceRule[];
  default?: string;
}

export interface FsmInvokeState {
  type: 'invoke';
  process: string;
  assign?: string;
  next: string;
}

export interface FsmCallState {
  type: 'call';
  service: string;
  method: string;
  url?: string;
  next: string;
}

export interface FsmAssignState {
  type: 'assign';
  set: Record<string, unknown>;
  next: string;
}

export interface FsmEndState {
  type: 'end';
  status?: string;
  outcome?: string;
}

export type FsmState =
  | FsmInputState
  | FsmOutputState
  | FsmChoiceState
  | FsmInvokeState
  | FsmCallState
  | FsmAssignState
  | FsmEndState;

export interface FsmProcess {
  start: string;
  vars?: Record<string, unknown>;
  states: Record<string, FsmState>;
}

export interface WorkflowDefinition {
  workflow_id: string;
  schema?: string;
  id: string;
  version?: string;
  entry: string;
  executor?: string;
  processes: Record<string, FsmProcess>;
}
