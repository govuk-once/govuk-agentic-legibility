import type { AutonomyPolicy, RunStateDTO } from '$lib/types';
import { createConversation, type Conversation } from './run-turn';

export interface ChatSession {
  conversation: Conversation;
  sessionState: RunStateDTO | null;
}

// In-memory, per-process — same rigor bar as the agentic.py `_autonomy_config`
// module dict it replaces (lost on redeploy, not shared across instances).
const chatSessions = new Map<string, ChatSession>();

export function getChatSession(conversationId: string): ChatSession {
  let session = chatSessions.get(conversationId);
  if (!session) {
    session = { conversation: createConversation([]), sessionState: null };
    chatSessions.set(conversationId, session);
  }
  return session;
}

export interface AutonomyConfig {
  policy: AutonomyPolicy;
  profile_fixture: string;
  preseed: string;
}

const autonomyConfigs = new Map<string, AutonomyConfig>();

export function setAutonomyConfig(workflowId: string, config: AutonomyConfig): void {
  autonomyConfigs.set(workflowId, config);
}

export function getAutonomyConfig(workflowId: string): AutonomyConfig | undefined {
  return autonomyConfigs.get(workflowId);
}
