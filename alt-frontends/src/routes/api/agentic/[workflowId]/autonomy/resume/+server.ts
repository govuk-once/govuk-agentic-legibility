import { getRunState } from '$lib/api/client';
import { buildAgenticTools } from '$lib/server/agent/agentic-tools';
import { buildContextualPrompt } from '$lib/server/agent/contextual-prompt';
import { getAutonomyConfig } from '$lib/server/agent/conversation-store';
import { loadProfileConversation } from '$lib/server/agent/profile-fixture';
import { createConversation, stepConversation, type SeedTurn } from '$lib/server/agent/run-turn';
import { SYSTEM_PROMPT } from '$lib/server/agent/system-prompt';
import type { ToolContext } from '$lib/server/agent/tool-defs';
import type { RunEvent, RunStateDTO } from '$lib/types';
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Each step may resolve several fields (see the instruction below), but a
// full journey like MA1 has 30+ inputs, so leave headroom for one-per-step models.
const MAX_AUTONOMOUS_STEPS = 60;

function seedHistory(profileFixture: string, preseed: string): SeedTurn[] {
  const history: SeedTurn[] = profileFixture ? loadProfileConversation(profileFixture) : [];
  if (preseed) {
    history.push(
      {
        role: 'user',
        text:
          'Before you start, here are facts about me to use when answering the questions ' +
          `in this application:\n\n${preseed}`
      },
      { role: 'assistant', text: "Thanks — I'll use those facts to answer on your behalf." }
    );
  }
  return history;
}

function sourceLabel(profileFixture: string, preseed: string): string {
  return [profileFixture && `profile.${profileFixture}`, preseed && 'preseed'].filter(Boolean).join(' + ');
}

// Direct port of durable_poc/agent/api/routes/agentic.py:resume_autonomy's SSE loop.
export const POST: RequestHandler = async ({ params }) => {
  const workflowId = params.workflowId;
  const config = getAutonomyConfig(workflowId);
  if (!config) {
    return json({ detail: 'Call POST /api/agentic/{id}/autonomy first' }, { status: 400 });
  }

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      const emit = (event: RunEvent) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      };

      let sessionState: RunStateDTO | null = null;
      const ctx: ToolContext = {
        getSessionState: () => sessionState,
        updateSessionState: (_workflowId, state) => {
          sessionState = state;
        },
        trace: () => {
          // Matches agentic.py:resume_autonomy's own on_trace, which only
          // watches for escalate_to_human rather than forwarding every trace.
        }
      };

      const conversation = createConversation(seedHistory(config.profile_fixture, config.preseed));
      const resolvedFrom = sourceLabel(config.profile_fixture, config.preseed);
      // The shared run loops rethrow tool errors, which suits chat (the error is
      // shown to the user) but would end an unattended step on the first
      // rejected value. Here a rejection goes back to the agent as a tool
      // result instead, so it can correct the value or escalate.
      const tools = buildAgenticTools(ctx).map((tool) =>
        tool.name !== 'submit_input'
          ? tool
          : {
              ...tool,
              execute: async (input: { token?: string; value?: unknown }) => {
                let result: unknown;
                try {
                  result = await tool.execute(input);
                } catch (error) {
                  const message = error instanceof Error ? error.message : String(error);
                  emit({
                    type: 'trace',
                    category: 'ENGINE',
                    summary: `Rejected value for [${input.token}]: ${message}`,
                    detail: { token: input.token, value: input.value, error: message }
                  });
                  return { rejected: true, error: message, awaiting: sessionState?.awaiting ?? null };
                }
                // Emitted per submission, not per step, so a step that resolves
                // several fields shows each as it lands and none are lost if it fails.
                emit({
                  type: 'trace',
                  category: 'AGENT',
                  summary: `Autonomously resolved field [${input.token}]`,
                  detail: { resolved_from: resolvedFrom, token: input.token, value: input.value }
                });
                return result;
              }
            }
      );

      try {
        for (let step = 0; step < MAX_AUTONOMOUS_STEPS; step++) {
          let state: RunStateDTO;
          try {
            state = await getRunState(workflowId);
          } catch (error) {
            emit({
              type: 'trace',
              category: 'ENGINE',
              summary: 'Run not found',
              detail: error instanceof Error ? error.message : String(error)
            });
            return;
          }
          sessionState = state;

          const awaiting = state.awaiting;
          if (!awaiting) {
            emit({ type: 'completed', status: state.status ?? 'COMPLETE' });
            return;
          }

          const beforeToken = awaiting.token;

          const instruction =
            'Resolve the field currently awaiting input autonomously, ' +
            'using only the seeded profile conversation and any facts I gave you ' +
            'up front as your source of facts — do not invent values. Policy: autonomy_level=' +
            `${config.policy.autonomy_level}, notify_categories=` +
            `${JSON.stringify(config.policy.notify_categories)}. If you cannot confidently ` +
            'resolve this field from those facts, or it falls in a notify ' +
            'category, call escalate_to_human with a short reason instead ' +
            'of guessing. Otherwise call submit_input. If submit_input returns a new ' +
            'field awaiting input that you can also resolve the same way, keep calling ' +
            'submit_input for it in this turn; stop when you escalate or nothing is awaiting.';

          let toolCalls;
          try {
            // As agentic.py's `agent.respond(instruction, context=state)`: pins the
            // agent to this run's id and token, rather than leaving it to pick one
            // from list_active_workflows.
            const result = await stepConversation(
              conversation,
              buildContextualPrompt(instruction, state),
              SYSTEM_PROMPT,
              tools
            );
            toolCalls = result.toolCalls;
          } catch (error) {
            emit({
              type: 'trace',
              category: 'AGENT',
              summary: 'Autonomous step failed',
              detail: error instanceof Error ? error.message : String(error)
            });
            return;
          }


          // The agent may have moved several fields on before escalating, so
          // hand the human whichever field is awaiting now, not the one this step began on.
          const newAwaiting = (sessionState as RunStateDTO | null)?.awaiting ?? null;
          const newToken = newAwaiting?.token ?? null;

          const escalationCall = toolCalls.find((c) => c.name === 'escalate_to_human');
          if (escalationCall) {
            const escalationResult = escalationCall.result as { reason?: string };
            const pending = newAwaiting ?? awaiting;
            emit({
              type: 'escalation',
              category: 'AGENT',
              summary: 'Escalated to human',
              detail: {
                reason: escalationResult?.reason,
                token: pending.token,
                prompt: pending.prompt,
                schema: pending.schema
              }
            });
            return;
          }

          if (newToken === beforeToken) {
            emit({
              type: 'escalation',
              category: 'AGENT',
              summary: 'No progress made; escalating',
              detail: {
                reason: 'Agent neither submitted nor escalated.',
                token: beforeToken,
                prompt: awaiting.prompt,
                schema: awaiting.schema
              }
            });
            return;
          }
        }

        emit({
          type: 'trace',
          category: 'ENGINE',
          summary: `Reached max autonomous steps (${MAX_AUTONOMOUS_STEPS})`
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
