import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { env } from '$env/dynamic/private';

export class InvalidProfileFixtureError extends Error {}
export class ProfileFixtureNotFoundError extends Error {}

export interface ProfileConversationTurn {
  role: 'user' | 'assistant';
  text: string;
}

export function scenariosRoot(): string {
  const override = env.DURABLE_POC_ROOT;
  const durablePocRoot = override ? path.resolve(override) : path.resolve(process.cwd(), '..', 'durable_poc');
  return path.join(durablePocRoot, 'evaluation', 'scenarios');
}

// Port of durable_poc/agent/api/routes/agentic.py:_load_profile_conversation,
// reading the fixture straight off disk instead of via a Python endpoint.
export function loadProfileConversation(profileFixture: string): ProfileConversationTurn[] {
  const root = scenariosRoot();
  const fixtureDir = path.resolve(root, profileFixture);
  const relative = path.relative(root, fixtureDir);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new InvalidProfileFixtureError(`Invalid profile_fixture path: ${profileFixture}`);
  }

  const conversationPath = path.join(fixtureDir, 'conversation.json');
  if (!existsSync(conversationPath)) {
    throw new ProfileFixtureNotFoundError(`No conversation.json for profile_fixture: ${profileFixture}`);
  }

  const data = JSON.parse(readFileSync(conversationPath, 'utf-8')) as {
    conversation?: Array<{ role: string; content: string }>;
  };
  const turns = data.conversation ?? [];

  return turns
    .filter((turn) => turn.role === 'user' || turn.role === 'assistant')
    .map((turn) => ({
      role: turn.role as 'user' | 'assistant',
      text: turn.content
    }));
}
