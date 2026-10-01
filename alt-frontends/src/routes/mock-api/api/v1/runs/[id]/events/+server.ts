import { watchRunStream } from '$lib/server/mock-executor/events';
import { requireMock } from '$lib/server/mock-executor/http';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = ({ params, request }) => {
  requireMock();
  return new Response(watchRunStream(params.id, request.signal), {
    headers: {
      'content-type': 'text/event-stream',
      'cache-control': 'no-cache',
      connection: 'keep-alive'
    }
  });
};
