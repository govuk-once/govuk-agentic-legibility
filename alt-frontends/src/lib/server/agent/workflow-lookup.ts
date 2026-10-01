import { getWorkflowDefinition, listWorkflows } from '$lib/api/client';
import type { WorkflowDefinition } from '$lib/graph/fsm';

// Port of durable_poc/agent/tools.py:find_workflow_by_intent.
export async function findWorkflowByIntent(domainKeyword: string): Promise<WorkflowDefinition> {
  const workflows = await listWorkflows();
  const keyword = domainKeyword.trim().toLowerCase();

  for (const wf of workflows as unknown[]) {
    if (typeof wf === 'string') {
      if (wf.toLowerCase().includes(keyword)) {
        return getWorkflowDefinition(wf);
      }
      continue;
    }

    if (wf && typeof wf === 'object') {
      const w = wf as Record<string, unknown>;
      const wfId = String(w.id ?? '').toLowerCase();
      const wfSlug = String(w.slug ?? '').toLowerCase();
      const wfName = String(w.name ?? '').toLowerCase();

      if (wfId.includes(keyword) || wfSlug.includes(keyword) || wfName.includes(keyword)) {
        const targetId = (w.id ?? w.slug ?? wfId) as string;
        return getWorkflowDefinition(String(targetId));
      }
    }
  }

  throw new Error(`No workflow found matching keyword: ${domainKeyword}`);
}

function looksLikeIdentifier(workflowId: string): boolean {
  return /^\d+$/.test(workflowId) || workflowId.includes('.') || workflowId.includes('-');
}

// Port of durable_poc/agent/tools.py:get_workflow_definition's keyword-search fallback.
export async function resolveWorkflowDefinition(workflowId: string): Promise<WorkflowDefinition> {
  if (!looksLikeIdentifier(workflowId)) {
    return findWorkflowByIntent(workflowId);
  }
  return getWorkflowDefinition(workflowId);
}
