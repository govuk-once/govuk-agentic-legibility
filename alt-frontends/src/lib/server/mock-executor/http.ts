import { error, json } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { seedRunsFromCheckpoints } from './definitions';

export function isMockEnabled(): boolean {
  return env.DURABLE_MOCK === '1' || env.DURABLE_MOCK === 'true';
}

// Every /mock-api handler calls this first: it 404s unless mock mode is on,
// so these routes are inert in normal dev and in production builds.
export function requireMock(): void {
  if (!isMockEnabled()) error(404, 'Not found');
  seedRunsFromCheckpoints();
}

// FastAPI's error shape, which client.ts's `request()` reads `detail` from.
export function detail(status: number, message: string): Response {
  return json({ detail: message }, { status });
}
