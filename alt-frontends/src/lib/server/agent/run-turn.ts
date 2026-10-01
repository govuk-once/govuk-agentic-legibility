import { env } from '$env/dynamic/private';
import {
  createBedrockConversation,
  stepBedrockConversation,
  type BedrockConversation
} from './run-loop-bedrock';
import {
  createOpenRouterConversation,
  stepOpenRouterConversation,
  type OpenRouterConversation
} from './run-loop-openrouter';
import type { ToolDef, ToolInvocation } from './tool-defs';

export type Conversation = BedrockConversation | OpenRouterConversation;

export interface SeedTurn {
  role: 'user' | 'assistant';
  text: string;
}

const DEFAULT_BEDROCK_MODEL_ID = 'anthropic.claude-sonnet-5';
const DEFAULT_AWS_REGION = 'us-east-1';
const DEFAULT_OPENROUTER_MODEL_ID = 'anthropic/claude-sonnet-5';

// Mirrors durable_poc/agent/api/deps.py:_dev_model_override's exact env-gating:
// OpenRouter only if OPENROUTER_API_KEY is set, Bedrock unconditionally otherwise.
export function createConversation(history: SeedTurn[] = []): Conversation {
  if (env.OPENROUTER_API_KEY) {
    return createOpenRouterConversation(
      history.map((turn) => ({ role: turn.role, content: turn.text }))
    );
  }
  return createBedrockConversation(
    history.map((turn) => ({ role: turn.role, content: [{ type: 'text', text: turn.text }] }))
  );
}

export async function stepConversation(
  conversation: Conversation,
  userPrompt: string,
  systemPrompt: string,
  tools: ToolDef[]
): Promise<{ responseText: string; toolCalls: ToolInvocation[] }> {
  if (conversation.provider === 'openrouter') {
    return stepOpenRouterConversation(
      conversation,
      userPrompt,
      systemPrompt,
      tools,
      env.OPENROUTER_API_KEY as string,
      env.OPENROUTER_MODEL_ID || DEFAULT_OPENROUTER_MODEL_ID
    );
  }
  return stepBedrockConversation(
    conversation,
    userPrompt,
    systemPrompt,
    tools,
    env.BEDROCK_MODEL_ID || DEFAULT_BEDROCK_MODEL_ID,
    env.AWS_REGION || DEFAULT_AWS_REGION
  );
}
