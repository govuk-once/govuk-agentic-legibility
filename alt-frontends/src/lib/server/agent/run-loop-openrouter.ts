import OpenAI from 'openai';
import type { ToolDef, ToolInvocation } from './tool-defs';

const MAX_TOOL_ITERATIONS = 8;

export interface OpenRouterToolCall {
  id: string;
  type: 'function';
  function: { name: string; arguments: string };
}

export interface OpenRouterMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_calls?: OpenRouterToolCall[];
  tool_call_id?: string;
}

export interface OpenRouterConversation {
  provider: 'openrouter';
  messages: OpenRouterMessage[];
}

export function createOpenRouterConversation(
  history: OpenRouterMessage[] = []
): OpenRouterConversation {
  return { provider: 'openrouter', messages: [...history] };
}

let cachedClient: OpenAI | null = null;
function getClient(apiKey: string): OpenAI {
  if (!cachedClient) {
    cachedClient = new OpenAI({ apiKey, baseURL: 'https://openrouter.ai/api/v1' });
  }
  return cachedClient;
}

function toOpenAiTools(tools: ToolDef[]) {
  return tools.map((t) => ({
    type: 'function' as const,
    function: {
      name: t.name,
      description: t.description,
      parameters: t.parameters
    }
  }));
}

export async function stepOpenRouterConversation(
  conversation: OpenRouterConversation,
  userPrompt: string,
  systemPrompt: string,
  tools: ToolDef[],
  apiKey: string,
  modelId: string
): Promise<{ responseText: string; toolCalls: ToolInvocation[] }> {
  const client = getClient(apiKey);
  const openAiTools = toOpenAiTools(tools);
  const toolCalls: ToolInvocation[] = [];

  if (!conversation.messages.some((m) => m.role === 'system')) {
    conversation.messages.unshift({ role: 'system', content: systemPrompt });
  }
  conversation.messages.push({ role: 'user', content: userPrompt });

  let responseText = '';

  for (let iteration = 0; iteration < MAX_TOOL_ITERATIONS; iteration++) {
    const response = await client.chat.completions.create({
      model: modelId,
      messages: conversation.messages as any,
      tools: openAiTools as any
    });

    const choice = response.choices[0];
    const message = choice.message;

    conversation.messages.push({
      role: 'assistant',
      content: message.content ?? null,
      tool_calls: message.tool_calls as OpenRouterToolCall[] | undefined
    });

    responseText = (message.content ?? '').trim();

    if (choice.finish_reason !== 'tool_calls' || !message.tool_calls?.length) {
      return { responseText, toolCalls };
    }

    const calls = message.tool_calls as unknown as OpenRouterToolCall[];
    for (const call of calls) {
      const toolDef = tools.find((t) => t.name === call.function.name);
      if (!toolDef) {
        conversation.messages.push({
          role: 'tool',
          tool_call_id: call.id,
          content: `Unknown tool: ${call.function.name}`
        });
        continue;
      }

      let parsedInput: unknown;
      try {
        parsedInput = JSON.parse(call.function.arguments || '{}');
      } catch {
        parsedInput = {};
      }

      try {
        const result = await toolDef.execute(parsedInput);
        toolCalls.push({ name: toolDef.name, input: parsedInput, result });
        conversation.messages.push({
          role: 'tool',
          tool_call_id: call.id,
          content: JSON.stringify(result)
        });
      } catch (e) {
        conversation.messages.push({
          role: 'tool',
          tool_call_id: call.id,
          content: e instanceof Error ? e.message : String(e)
        });
        throw e;
      }
    }
  }

  return { responseText, toolCalls };
}
