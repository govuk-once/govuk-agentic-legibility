import { json } from '@sveltejs/kit';
import { runs, runState } from '$lib/server/mock-executor/engine';
import { detail, requireMock } from '$lib/server/mock-executor/http';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = ({ params }) => {
  requireMock();
  const run = runs.get(params.id);
  return run ? json(runState(run)) : detail(404, `Run not found: ${params.id}`);
};
