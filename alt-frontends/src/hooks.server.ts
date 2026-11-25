import type { Handle } from '@sveltejs/kit';
import { isMockEnabled } from '$lib/server/mock-executor/http';

// Mock mode (`pnpm dev:mock`) serves a stand-in executor under /mock-api. The
// browser reaches it via PUBLIC_DURABLE_API_URL, which may name a different
// host than the page (localhost vs 127.0.0.1), so it gets permissive CORS the
// way durable_poc's FastAPI app does. Outside mock mode this is a pass-through.
const CORS_HEADERS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, POST, OPTIONS',
  'access-control-allow-headers': 'content-type'
};

export const handle: Handle = async ({ event, resolve }) => {
  if (!event.url.pathname.startsWith('/mock-api/') || !isMockEnabled()) {
    return resolve(event);
  }
  if (event.request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }
  const response = await resolve(event);
  for (const [key, value] of Object.entries(CORS_HEADERS)) response.headers.set(key, value);
  return response;
};
