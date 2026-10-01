import { json } from '@sveltejs/kit';
import { getRunState } from '$lib/api/client';
import { cleanTextPipes } from '$lib/server/agent/clean-text';
import { getChatSession } from '$lib/server/agent/conversation-store';
import { buildContextualPrompt } from '$lib/server/agent/contextual-prompt';
import { getOptionsFromState } from '$lib/server/agent/options-from-state';
import { stepConversation } from '$lib/server/agent/run-turn';
import { SYSTEM_PROMPT } from '$lib/server/agent/system-prompt';
import { buildChatTools } from '$lib/server/agent/tools';
import type { ToolContext } from '$lib/server/agent/tool-defs';
import type { RunEvent } from '$lib/types';
import type { RequestHandler } from './$types';

interface ChatRequestBody {
  conversationId: string;
  message?: string;
  action?: 'resume';
  workflowId?: string;
}

// Replaces WS /chat (durable_poc/agent/api/routes/chat_ws.py) with a
// SvelteKit-hosted turn: `action: 'resume'` mirrors the WS's `{action:
// 'resume', workflow_id}` message (synchronous, no LLM turn); a `message`
// mirrors one WS user-message turn, streamed back as SSE `RunEvent`s.
export const POST: RequestHandler = async ({ request }) => {
  const body = (await request.json()) as ChatRequestBody;
  if (!body.conversationId) {
    return json({ error: 'conversationId is required' }, { status: 400 });
  }
  const session = getChatSession(body.conversationId);

  if (body.action === 'resume') {
    if (!body.workflowId) {
      return json({ error: 'workflowId is required to resume' }, { status: 400 });
    }
    const state = await getRunState(body.workflowId);
    session.sessionState = state;
    const opts = getOptionsFromState(state);
    return json({ workflowId: body.workflowId, state, options: opts });
  }

  const userMsg = (body.message ?? '').trim();
  if (!userMsg) {
    return json({ error: 'message is required' }, { status: 400 });
  }

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      const emit = (event: RunEvent) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      };

      const previousWorkflowId = session.sessionState?.workflow_id ?? null;

      const ctx: ToolContext = {
        getSessionState: () => session.sessionState,
        updateSessionState: (_workflowId, state) => {
          session.sessionState = state;
        },
        trace: (category, summary, detail) => {
          emit({ type: 'trace', category, summary, detail });
        }
      };

      try {
        emit({
          type: 'trace',
          category: 'USER',
          summary: 'Submitted Natural Language Input',
          detail: userMsg
        });
        emit({ type: 'trace', category: 'AGENT', summary: 'Invoking Bedrock LLM with user context...' });

        const contextualPrompt = buildContextualPrompt(userMsg, session.sessionState);
        const tools = buildChatTools(ctx);
        const { responseText } = await stepConversation(
          session.conversation,
          contextualPrompt,
          SYSTEM_PROMPT,
          tools
        );

        if (session.sessionState?.workflow_id && session.sessionState.workflow_id !== previousWorkflowId) {
          emit({
            type: 'trace',
            category: 'SYSTEM',
            summary: 'Active Workflow',
            detail: session.sessionState.workflow_id
          });
        }

        if (responseText && responseText.trim()) {
          const cleanResponse = cleanTextPipes(responseText);
          if (cleanResponse) {
            emit({ type: 'message', role: 'assistant', text: cleanResponse });
            emit({ type: 'trace', category: 'AGENT', summary: 'Agent emitted response text', detail: cleanResponse });
          }
        }

        const opts = getOptionsFromState(session.sessionState);
        emit({ type: 'options', kind: opts.kind, options: opts.options });
      } catch (error) {
        emit({
          type: 'trace',
          category: 'AGENT',
          summary: 'Agent turn failed',
          detail: error instanceof Error ? error.message : String(error)
        });
      } finally {
        controller.close();
      }
    }
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive'
    }
  });
};
