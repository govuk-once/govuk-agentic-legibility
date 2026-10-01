import { json } from '@sveltejs/kit';
import { loadDefinitions } from '$lib/server/mock-executor/definitions';
import { requireMock } from '$lib/server/mock-executor/http';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = () => {
  requireMock();
  return json(
    loadDefinitions().map(({ id, slug, name, workflow_id, version }) => ({ id, slug, name, workflow_id, version }))
  );
};
