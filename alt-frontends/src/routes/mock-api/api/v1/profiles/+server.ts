import { json } from '@sveltejs/kit';
import { listProfiles } from '$lib/server/mock-executor/definitions';
import { requireMock } from '$lib/server/mock-executor/http';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = () => {
  requireMock();
  return json(listProfiles());
};
