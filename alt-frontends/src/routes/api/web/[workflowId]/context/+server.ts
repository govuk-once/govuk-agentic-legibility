import { json } from '@sveltejs/kit';
import { getWebContext, setWebContext } from '$lib/server/agent/web-context-store';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params }) => {
  return json({ context: getWebContext(params.workflowId!) });
};

export const POST: RequestHandler = async ({ params, request }) => {
  const body = (await request.json()) as { context?: string };
  const context = (body.context ?? '').trim();
  setWebContext(params.workflowId!, context);
  return json({ context });
};
