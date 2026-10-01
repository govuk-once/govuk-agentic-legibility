import { AnthropicBedrock } from '@anthropic-ai/bedrock-sdk';
import type { ToolDef, ToolInvocation } from './tool-defs';

const MAX_TOOL_ITERATIONS = 8;

export interface BedrockContentBlock {
  type: 'text' | 'tool_use' | 'tool_result';
  text?: string;
  id?: string;
  name?: string;
  input?: unknown;
  tool_use_id?: string;
  content?: string;
  is_error?: boolean;
}

export interface BedrockMessage {
  role: 'user' | 'assistant';
  content: string | BedrockContentBlock[];
}

export interface BedrockConversation {
  provider: 'bedrock';
  messages: BedrockMessage[];
}

export function createBedrockConversation(history: BedrockMessage[] = []): BedrockConversation {
  return { provider: 'bedrock', messages: [...history] };
}

let cachedClient: AnthropicBedrock | null = null;
function getClient(region: string): AnthropicBedrock {
  if (!cachedClient) {
    cachedClient = new AnthropicBedrock({ awsRegion: region });
  }
  return cachedClient;
}

function toAnthropicTools(tools: ToolDef[]) {
  return tools.map((t) => ({
    name: t.name,
    description: t.description,
    input_schema: t.parameters
  }));
}

export async function stepBedrockConversation(
  conversation: BedrockConversation,
  userPrompt: string,
  systemPrompt: string,
  tools: ToolDef[],
  modelId: string,
  region: string
): Promise<{ responseText: string; toolCalls: ToolInvocation[] }> {
  const client = getClient(region);
  const anthropicTools = toAnthropicTools(tools);
  const toolCalls: ToolInvocation[] = [];

  conversation.messages.push({ role: 'user', content: userPrompt });

  let responseText = '';

  for (let iteration = 0; iteration < MAX_TOOL_ITERATIONS; iteration++) {
    const response = await client.messages.create({
      model: modelId,
      max_tokens: 4096,
      system: systemPrompt,
      messages: conversation.messages as any,
      tools: anthropicTools as any
    });

    const content = response.content as unknown as BedrockContentBlock[];
    conversation.messages.push({ role: 'assistant', content: content as BedrockContentBlock[] });

    const textBlocks = content.filter((b) => b.type === 'text').map((b) => b.text ?? '');
    responseText = textBlocks.join('\n').trim();

    if (response.stop_reason !== 'tool_use') {
      return { responseText, toolCalls };
    }

    const toolUseBlocks = content.filter((b) => b.type === 'tool_use');
    const resultBlocks: BedrockContentBlock[] = [];

    for (const block of toolUseBlocks) {
      const toolDef = tools.find((t) => t.name === block.name);
      if (!toolDef) {
        resultBlocks.push({
          type: 'tool_result',
          tool_use_id: block.id,
          content: `Unknown tool: ${block.name}`,
          is_error: true
        });
        continue;
      }

      try {
        const result = await toolDef.execute(block.input);
        toolCalls.push({ name: toolDef.name, input: block.input, result });
        resultBlocks.push({
          type: 'tool_result',
          tool_use_id: block.id,
          content: JSON.stringify(result)
        });
      } catch (e) {
        conversation.messages.push({
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: block.id,
              content: e instanceof Error ? e.message : String(e),
              is_error: true
            }
          ]
        });
        throw e;
      }
    }

    conversation.messages.push({ role: 'user', content: resultBlocks });
  }

  return { responseText, toolCalls };
}
