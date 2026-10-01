import { json } from '@sveltejs/kit';
import { createRun, runs } from '$lib/server/mock-executor/engine';
import { findDefinition } from '$lib/server/mock-executor/definitions';
import { detail, requireMock } from '$lib/server/mock-executor/http';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = () => {
  requireMock();
  return json(
    [...runs.values()].filter((run) => run.status === 'RUNNING').map((run) => ({ id: run.id, status: run.status }))
  );
};

export const POST: RequestHandler = async ({ request }) => {
  requireMock();
  const body = (await request.json().catch(() => ({}))) as { workflow_id?: string };
  const definition = body.workflow_id ? findDefinition(String(body.workflow_id)) : null;
  if (!definition) return detail(502, `Workflow not found: ${body.workflow_id}`);
  const run = createRun(definition);
  return json({ workflow_id: run.id }, { status: 201 });
};
