import { json } from '@sveltejs/kit';
import { MockInputError, runs, runState, submitInput } from '$lib/server/mock-executor/engine';
import { detail, requireMock } from '$lib/server/mock-executor/http';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ params, request }) => {
  requireMock();
  const run = runs.get(params.id);
  if (!run) return detail(404, `Run not found: ${params.id}`);
  const body = (await request.json().catch(() => ({}))) as { token?: string; value?: unknown };
  try {
    submitInput(run, String(body.token ?? ''), body.value);
  } catch (error) {
    if (error instanceof MockInputError) return detail(409, error.message);
    throw error;
  }
  return json(runState(run));
};
