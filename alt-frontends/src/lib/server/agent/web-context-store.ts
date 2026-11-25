// In-memory, per-process — same rigor bar as conversation-store.ts's
// `chatSessions`/`autonomyConfigs` maps (lost on redeploy, not shared across
// instances). Holds the free-text notes a /web user opts into providing so
// the prefill route can suggest field values from them.
const webContexts = new Map<string, string>();

export function setWebContext(workflowId: string, context: string): void {
  webContexts.set(workflowId, context);
}

export function getWebContext(workflowId: string): string | null {
  return webContexts.get(workflowId) ?? null;
}
