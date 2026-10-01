import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { env } from '$env/dynamic/private';
import type { WorkflowDefinition } from '$lib/graph/fsm';
import type { ProfileSummary } from '$lib/types';
import { scenariosRoot } from '$lib/server/agent/profile-fixture';
import { restoreRun, runs } from './engine';

// Stands in for the workflow server's registry: reads the same
// `*_schema.json` definitions the real worker executes straight from the
// durable_poc checkout (DURABLE_POC_ROOT, default ../durable_poc).

export type MockWorkflow = WorkflowDefinition & { name: string; slug: string };

function durablePocRoot(): string {
  return env.DURABLE_POC_ROOT ? path.resolve(env.DURABLE_POC_ROOT) : path.resolve(process.cwd(), '..', 'durable_poc');
}

function humanise(id: string, file: string): string {
  const [dept, ...rest] = id.split('.');
  const words = rest.join(' ').replace(/_/g, ' ');
  const suffix = file.includes('_adv_') ? ' (advanced)' : '';
  return `${dept.toUpperCase()}: ${words.charAt(0).toUpperCase()}${words.slice(1)}${suffix}`;
}

// Re-read on every call so edits to the definitions show up without a restart.
export function loadDefinitions(): MockWorkflow[] {
  const root = durablePocRoot();
  if (!existsSync(root)) return [];
  const files = readdirSync(root).filter((f) => f.endsWith('_schema.json'));
  const parsed = files.flatMap((file) => {
    try {
      const def = JSON.parse(readFileSync(path.join(root, file), 'utf-8')) as WorkflowDefinition;
      return def.id && def.processes ? [{ file, def }] : [];
    } catch {
      return [];
    }
  });
  // Two files can share an id (dvla_coa vs dvla_coa_adv); the highest version
  // keeps the plain id and the rest get a version suffix so each is addressable.
  parsed.sort((a, b) => String(b.def.version ?? '').localeCompare(String(a.def.version ?? ''), undefined, { numeric: true }));
  const seen = new Set<string>();
  return parsed.map(({ file, def }) => {
    const id = seen.has(def.id) ? `${def.id}.v${def.version}` : def.id;
    seen.add(id);
    return { ...def, id, slug: id, name: humanise(def.id, file) };
  });
}

/** Resolves a definition id, a run id (`sfsm-<id>-<hex>`) or a keyword. */
export function findDefinition(key: string): MockWorkflow | null {
  const run = runs.get(key);
  if (run) return run.definition as MockWorkflow;

  const defs = loadDefinitions();
  const runMatch = /^sfsm-(.+)-[0-9a-f]{8}$/.exec(key);
  const wanted = runMatch ? runMatch[1] : key;
  const lower = wanted.toLowerCase();
  return (
    defs.find((d) => d.id === wanted) ??
    defs.find((d) => String(d.workflow_id) === wanted) ??
    defs.find((d) => d.id.toLowerCase().includes(lower) || d.name.toLowerCase().includes(lower)) ??
    null
  );
}

function scenarioDirs(): string[] {
  const root = scenariosRoot();
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .flatMap((journey) =>
      readdirSync(path.join(root, journey.name), { withFileTypes: true })
        .filter((d) => d.isDirectory())
        .map((d) => `${journey.name}/${d.name}`)
    )
    .sort();
}

export function listProfiles(): ProfileSummary[] {
  const root = scenariosRoot();
  return scenarioDirs().flatMap((fixture) => {
    try {
      const data = JSON.parse(readFileSync(path.join(root, fixture, 'conversation.json'), 'utf-8'));
      return [{ fixture, title: data.title ?? fixture, journey_id: data.journey_id ?? '' }];
    } catch {
      return [];
    }
  });
}

const seeded = globalThis as unknown as { __durableMockSeeded?: boolean };

/**
 * Pre-populates the run store with one mid-journey run per evaluation
 * checkpoint, so run pickers and resume flows have something to show on a
 * fresh server. Run ids are derived from the fixture path, so they're stable
 * across restarts and can be bookmarked.
 */
export function seedRunsFromCheckpoints(): void {
  if (seeded.__durableMockSeeded) return;
  seeded.__durableMockSeeded = true;

  const root = scenariosRoot();
  for (const fixture of scenarioDirs()) {
    const checkpointPath = path.join(root, fixture, 'checkpoint.json');
    if (!existsSync(checkpointPath)) continue;
    try {
      const checkpoint = JSON.parse(readFileSync(checkpointPath, 'utf-8'));
      let journeyId: string | undefined;
      try {
        journeyId = JSON.parse(readFileSync(path.join(root, fixture, 'conversation.json'), 'utf-8')).journey_id;
      } catch {
        // fall back to the checkpoint's source run id below
      }
      const definition = findDefinition(journeyId || checkpoint.source_workflow_id || '');
      if (!definition) continue;
      const hash = createHash('sha1').update(fixture).digest('hex').slice(0, 8);
      restoreRun(definition, `sfsm-${definition.id}-${hash}`, checkpoint);
    } catch (error) {
      console.warn(`[mock-executor] could not seed run from ${fixture}:`, error);
    }
  }
}
