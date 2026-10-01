import { json } from '@sveltejs/kit';
import { getAutonomyConfig, setAutonomyConfig } from '$lib/server/agent/conversation-store';
import {
  InvalidProfileFixtureError,
  ProfileFixtureNotFoundError,
  loadProfileConversation
} from '$lib/server/agent/profile-fixture';
import type { SetAutonomyRequest } from '$lib/types';
import type { RequestHandler } from './$types';

// Replaces POST /api/v1/runs/{id}/autonomy (durable_poc/agent/api/routes/agentic.py:set_autonomy).
// Unlike the Python route, a profile bundle is optional when pre-seeded facts are given.
export const POST: RequestHandler = async ({ request, params }) => {
  const workflowId = params.workflowId;
  const body = (await request.json()) as SetAutonomyRequest;
  const profileFixture = body.profile_fixture ?? '';
  const preseed = (body.preseed ?? '').trim();

  if (!profileFixture && !preseed) {
    return json({ detail: 'Choose a profile bundle or pre-seed some facts' }, { status: 400 });
  }

  if (profileFixture) {
    try {
      loadProfileConversation(profileFixture);
    } catch (error) {
      if (error instanceof InvalidProfileFixtureError) {
        return json({ detail: error.message }, { status: 400 });
      }
      if (error instanceof ProfileFixtureNotFoundError) {
        return json({ detail: error.message }, { status: 404 });
      }
      throw error;
    }
  }

  setAutonomyConfig(workflowId, { policy: body.policy, profile_fixture: profileFixture, preseed });

  return json({
    workflow_id: workflowId,
    policy: body.policy,
    profile_fixture: profileFixture,
    preseed
  });
};

export const GET: RequestHandler = async ({ params }) => {
  const config = getAutonomyConfig(params.workflowId);
  if (!config) {
    return json({ detail: 'No autonomy policy set for this workflow' }, { status: 404 });
  }
  return json({ workflow_id: params.workflowId, ...config });
};
