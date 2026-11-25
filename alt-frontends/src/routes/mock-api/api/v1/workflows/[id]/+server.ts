import { json } from '@sveltejs/kit';
import { findDefinition } from '$lib/server/mock-executor/definitions';
import { detail, requireMock } from '$lib/server/mock-executor/http';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = ({ params }) => {
  requireMock();
  const definition = findDefinition(params.id);
  return definition ? json(definition) : detail(404, `Workflow not found: ${params.id}`);
};
