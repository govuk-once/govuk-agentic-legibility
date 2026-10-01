import type { RunStateDTO } from '$lib/types';

// Port of durable_poc/agent/agent.py:build_contextual_prompt.
export function buildContextualPrompt(userMessage: string, context: RunStateDTO | null): string {
  if (!context) {
    return userMessage;
  }

  const workflowId = context.workflow_id ?? 'unknown';
  const awaiting = context.awaiting;

  const stateDescription = awaiting
    ? `Active workflow: ${workflowId}\n` +
      `Currently awaiting input:\n` +
      `  token: ${awaiting.token}\n` +
      `  prompt: ${awaiting.prompt}\n` +
      `  schema: ${JSON.stringify(awaiting.schema ?? {})}\n`
    : `Active workflow: ${workflowId}\n` +
      `The workflow is not currently awaiting input (processing background tasks or completed).\n`;

  return `${stateDescription}\nUser message: ${userMessage}`;
}
