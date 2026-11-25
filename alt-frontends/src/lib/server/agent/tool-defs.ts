import {
  getApiBaseUrl,
  getRunState,
  listActiveRuns,
  listWorkflows,
  startRun,
  submitRunInput
} from '$lib/api/client';
import type { RunStateDTO } from '$lib/types';
import { coerceValue } from './coerce-value';
import { findWorkflowByIntent, resolveWorkflowDefinition } from './workflow-lookup';

export interface ToolDef {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
  execute: (input: any) => Promise<unknown>;
}

export interface ToolContext {
  getSessionState: () => RunStateDTO | null;
  updateSessionState: (workflowId: string, state: RunStateDTO) => void;
  trace: (category: string, summary: string, detail?: unknown) => void;
}

export interface ToolInvocation {
  name: string;
  input: unknown;
  result: unknown;
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

// Port of durable_poc/agent/agent.py:_build_tools's 7 shared tool closures.
// Trace category/summary/detail text is kept verbatim from the Python source
// so TraceSidebar.svelte renders identically regardless of which backend ran.
export function buildBaseToolDefs(ctx: ToolContext): ToolDef[] {
  return [
    {
      name: 'list_available_workflows',
      description: 'Fetch all registered workflow definitions from the workflow server.',
      parameters: { type: 'object', properties: {} },
      execute: async () => {
        ctx.trace('AGENT', 'Selected Tool: list_available_workflows');
        try {
          return await listWorkflows();
        } catch (e) {
          ctx.trace('AGENT', 'Tool Error: list_available_workflows', errMsg(e));
          throw e;
        }
      }
    },
    {
      name: 'find_workflow_by_intent',
      description:
        "Search registered workflow definitions on the server by domain keyword (e.g. 'address', 'maternity').",
      parameters: {
        type: 'object',
        properties: {
          domain_keyword: {
            type: 'string',
            description: 'The keyword describing the service domain.'
          }
        },
        required: ['domain_keyword']
      },
      execute: async (input: { domain_keyword: string }) => {
        const { domain_keyword } = input;
        ctx.trace('AGENT', 'Selected Tool: find_workflow_by_intent', { keyword: domain_keyword });
        try {
          return await findWorkflowByIntent(domain_keyword);
        } catch (e) {
          ctx.trace('AGENT', 'Tool Error: find_workflow_by_intent', errMsg(e));
          throw e;
        }
      }
    },
    {
      name: 'get_workflow_definition',
      description:
        'Fetch a workflow definition from the server by its numeric ID or string slug identifier.',
      parameters: {
        type: 'object',
        properties: {
          workflow_id: {
            type: ['string', 'number'],
            description: 'The numeric workflow ID or string slug identifier.'
          }
        },
        required: ['workflow_id']
      },
      execute: async (input: { workflow_id: string | number }) => {
        const workflowId = String(input.workflow_id);
        ctx.trace('AGENT', 'Selected Tool: get_workflow_definition', {
          workflow_id: input.workflow_id
        });
        try {
          ctx.trace(
            'SYSTEM',
            'Fetching Workflow Definition from Server',
            `GET ${getApiBaseUrl()}/api/v1/workflows/${workflowId}`
          );
          const result = await resolveWorkflowDefinition(workflowId);
          const r = result as unknown as Record<string, unknown>;
          ctx.trace('SYSTEM', 'Fetched Workflow Definition', {
            id: r.id,
            version: r.version,
            entry: r.entry
          });
          return result;
        } catch (e) {
          ctx.trace('AGENT', 'Tool Error: get_workflow_definition', errMsg(e));
          throw e;
        }
      }
    },
    {
      name: 'start_workflow',
      description:
        'Fetch a workflow definition by numeric ID or string slug and start it on Temporal.',
      parameters: {
        type: 'object',
        properties: {
          workflow_id: {
            type: ['string', 'number'],
            description: 'The numeric workflow ID or string slug from the workflow server.'
          }
        },
        required: ['workflow_id']
      },
      execute: async (input: { workflow_id: string | number }) => {
        try {
          const { workflow_id: temporalWorkflowId } = await startRun(String(input.workflow_id));
          ctx.trace('ENGINE', 'Started Temporal Execution', { workflow_id: temporalWorkflowId });
          const state = await getRunState(temporalWorkflowId);
          ctx.updateSessionState(temporalWorkflowId, state);
          return { ...state, workflow_id: temporalWorkflowId };
        } catch (e) {
          ctx.trace('ENGINE', 'Start Workflow Failed', errMsg(e));
          throw e;
        }
      }
    },
    {
      name: 'get_workflow_state',
      description: 'Query the current state of a running workflow.',
      parameters: {
        type: 'object',
        properties: {
          workflow_id: { type: 'string', description: 'The Temporal workflow ID.' }
        },
        required: ['workflow_id']
      },
      execute: async (input: { workflow_id: string }) => {
        const { workflow_id } = input;
        ctx.trace('AGENT', 'Selected Tool: get_workflow_state', { workflow_id });
        let state: RunStateDTO;
        try {
          state = await getRunState(workflow_id);
        } catch (e) {
          ctx.trace('ENGINE', 'Get Workflow State Failed', errMsg(e));
          throw e;
        }
        ctx.updateSessionState(workflow_id, state);

        if (!state.awaiting) {
          return {
            workflow_id,
            status: state.status ?? 'RUNNING',
            awaiting: null,
            message: 'The workflow is processing background tasks or completed. Do not re-query.',
            transcript: state.transcript ?? []
          };
        }
        return state;
      }
    },
    {
      name: 'submit_input',
      description: 'Submit user input to a workflow and return the new workflow state.',
      parameters: {
        type: 'object',
        properties: {
          workflow_id: { type: 'string', description: 'The Temporal workflow ID.' },
          token: { type: 'string', description: 'The input token from the awaiting state.' },
          value: { description: 'The structured value to submit.' }
        },
        required: ['workflow_id', 'token', 'value']
      },
      execute: async (input: { workflow_id: string; token: string; value: unknown }) => {
        const { workflow_id, token, value } = input;
        const coercedValue = coerceValue(value, ctx.getSessionState());
        ctx.trace('AGENT', 'Selected Tool: submit_input', {
          workflow_id,
          token,
          raw_value: value,
          coerced_value: coercedValue
        });
        try {
          const state = await submitRunInput(workflow_id, token, coercedValue);
          ctx.trace('ENGINE', 'Temporal Update Accepted', { token });
          ctx.updateSessionState(workflow_id, state);
          return state;
        } catch (e) {
          ctx.trace('ENGINE', 'Temporal Update Rejected', errMsg(e));
          throw e;
        }
      }
    },
    {
      name: 'list_active_workflows',
      description: 'List running workflows that the user may want to resume.',
      parameters: { type: 'object', properties: {} },
      execute: async () => {
        ctx.trace('AGENT', 'Selected Tool: list_active_workflows');
        try {
          return await listActiveRuns();
        } catch (e) {
          ctx.trace('ENGINE', 'List Active Workflows Failed', errMsg(e));
          throw e;
        }
      }
    }
  ];
}

// Port of durable_poc/agent/agent.py:_build_tools's escalate_to_human closure —
// only added to the tool roster for the autonomous /agentic resume loop.
export function buildEscalationToolDef(ctx: ToolContext): ToolDef {
  return {
    name: 'escalate_to_human',
    description:
      'Flag the field currently awaiting input for a human to answer, instead of guessing ' +
      'or submitting an unconfident value.\n\n' +
      'Call this when the seeded profile has no confident answer for the current question, ' +
      'or when the field is sensitive enough (identity, payment, an irreversible action) that ' +
      'policy requires a human decision. Prefer this over a low-confidence submit_input call.',
    parameters: {
      type: 'object',
      properties: {
        reason: { type: 'string', description: 'Brief explanation of why this needs a human.' }
      },
      required: ['reason']
    },
    execute: async (input: { reason: string }) => {
      const { reason } = input;
      ctx.trace('AGENT', 'Selected Tool: escalate_to_human', { reason });
      return { escalated: true, reason };
    }
  };
}
