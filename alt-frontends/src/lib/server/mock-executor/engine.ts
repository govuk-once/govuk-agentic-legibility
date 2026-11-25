import { randomUUID } from 'node:crypto';
import type { WorkflowDefinition } from '$lib/graph/fsm';
import type { AwaitingInput, RunStateDTO, TranscriptEntry } from '$lib/types';
import {
  applyDateMath,
  interpolate,
  isoNaive,
  parseDuration,
  resolveDict,
  resolvePath,
  setPath
} from './paths';
import { evaluate } from './predicates';
import { callMockService } from './services';

// An in-memory stand-in for durable_poc's Temporal worker: a port of
// src/interpreter.py:SFSMInterpreter that walks the same JSON definitions
// synchronously instead of as a durable workflow. Runs live only as long as
// this dev server process. Behavioural differences from the real executor:
// `wait` states and non-transcript notifications are skipped, and `call`
// states are answered by `services.ts` rather than real HTTP.

type Vars = Record<string, unknown>;
// Definitions are loosely typed JSON here — fsm.ts's shapes only cover what
// the graph view needs, not every executor field (catch, timeout, return…).
type StateDef = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

interface Frame {
  process_id: string;
  state_id: string;
  vars: Vars;
  invoker: StateDef | null;
}

export type RunStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'TERMINATED';

export interface MockRun {
  id: string;
  definition: WorkflowDefinition;
  frames: Frame[];
  transcript: TranscriptEntry[];
  stepCounter: number;
  env: Vars;
  awaiting: AwaitingInput | null;
  status: RunStatus;
  result: unknown;
  timeoutHandle: ReturnType<typeof setTimeout> | null;
}

export class MockInputError extends Error {}

const MAX_TRANSCRIPT_LENGTH = 100;
// Guards against a definition that loops without ever reaching an input or end state.
const MAX_STEPS_PER_ADVANCE = 5000;
// setTimeout's ceiling; longer input timeouts (e.g. P7D reminders) just never fire.
const MAX_TIMER_MS = 2 ** 31 - 1;

// Pinned to globalThis so runs survive Vite's HMR re-evaluating this module.
const store = globalThis as unknown as { __durableMockRuns?: Map<string, MockRun> };
export const runs: Map<string, MockRun> = (store.__durableMockRuns ??= new Map());

const clone = <T>(value: T): T => structuredClone(value);
const now = () => isoNaive(new Date());

function processOf(run: MockRun, processId: string) {
  return (run.definition.processes as Record<string, { start: string; vars?: Vars; states: Record<string, StateDef> }>)[
    processId
  ];
}

export function createRun(definition: WorkflowDefinition, id?: string): MockRun {
  const entry = processOf({ definition } as MockRun, definition.entry);
  if (!entry) throw new Error(`Entry process '${definition.entry}' not found in processes definition`);
  const run: MockRun = {
    id: id ?? `sfsm-${definition.id ?? 'unknown'}-${randomUUID().slice(0, 8)}`,
    definition,
    frames: [{ process_id: definition.entry, state_id: entry.start, vars: clone(entry.vars ?? {}), invoker: null }],
    transcript: [],
    stepCounter: 0,
    env: {},
    awaiting: null,
    status: 'RUNNING',
    result: null,
    timeoutHandle: null
  };
  runs.set(run.id, run);
  advance(run);
  return run;
}

/** Rebuilds a run from an `evaluation_checkpoint` snapshot (evaluation/scenarios/*∕checkpoint.json). */
export function restoreRun(
  definition: WorkflowDefinition,
  id: string,
  checkpoint: {
    interpreter_state: {
      frames: Array<{ process_id: string; state_id: string; vars: Vars; invoker_state_id: string | null }>;
      transcript: TranscriptEntry[];
      step_counter: number;
      env?: Vars;
    };
  }
): MockRun {
  const snapshot = checkpoint.interpreter_state;
  const run: MockRun = {
    id,
    definition,
    frames: [],
    transcript: clone(snapshot.transcript ?? []),
    stepCounter: snapshot.step_counter ?? 0,
    env: clone(snapshot.env ?? {}),
    awaiting: null,
    status: 'RUNNING',
    result: null,
    timeoutHandle: null
  };
  snapshot.frames.forEach((frame, index) => {
    let invoker: StateDef | null = null;
    if (frame.invoker_state_id && index > 0) {
      const parent = processOf(run, snapshot.frames[index - 1].process_id);
      invoker = parent?.states[frame.invoker_state_id] ?? null;
    }
    run.frames.push({ process_id: frame.process_id, state_id: frame.state_id, vars: clone(frame.vars), invoker });
  });
  runs.set(run.id, run);
  advance(run);
  return run;
}

export function runState(run: MockRun): RunStateDTO {
  return {
    workflow_id: run.id,
    status: run.status,
    awaiting: run.awaiting ? clone(run.awaiting) : null,
    transcript: clone(run.transcript)
  };
}

function log(run: MockRun, message: string): void {
  run.transcript.push({ step: run.stepCounter, timestamp: now(), message });
  if (run.transcript.length > MAX_TRANSCRIPT_LENGTH) {
    run.transcript = run.transcript.slice(-MAX_TRANSCRIPT_LENGTH);
  }
}

function fail(run: MockRun, reason: string): void {
  console.warn(`[mock-executor] run ${run.id} failed: ${reason}`);
  log(run, `[ENGINE LOG] ❌ Workflow failed: ${reason}`);
  run.status = 'FAILED';
  run.awaiting = null;
}

function advance(run: MockRun): void {
  try {
    step(run);
  } catch (error) {
    fail(run, error instanceof Error ? error.message : String(error));
  }
}

function step(run: MockRun): void {
  for (let guard = 0; run.frames.length > 0; guard++) {
    if (guard > MAX_STEPS_PER_ADVANCE) {
      throw new Error(`Exceeded ${MAX_STEPS_PER_ADVANCE} steps without reaching an input or end state`);
    }
    run.stepCounter += 1;
    const frame = run.frames[run.frames.length - 1];
    const process = processOf(run, frame.process_id);
    if (!process) throw new Error(`Process '${frame.process_id}' not found`);
    const state = process.states[frame.state_id];
    if (!state) throw new Error(`State ${frame.state_id} not found in ${frame.process_id}`);

    // Shallow merge, as interpreter.py's `context.update(frame.vars)` is.
    const context: Vars = {
      input: frame.vars.input ?? {},
      env: run.env,
      workflow_id: run.id,
      step: run.stepCounter,
      __now__: now(),
      ...frame.vars
    };

    switch (state.type) {
      case 'input':
        awaitInput(run, frame, state, context);
        return;

      case 'output': {
        if (state.channel === 'transcript' || state.also_transcript) {
          log(run, interpolate(state.also_transcript || state.message || '', context));
        }
        frame.state_id = state.next;
        break;
      }

      case 'call': {
        const url = interpolate(state.url, context);
        const method = String(state.method);
        log(run, `[ENGINE LOG] 🌐 Dispatched HTTP ${method} request to service '${state.service}' (${url})`);
        const response = callMockService(state.service, method, url, resolveDict(state.body ?? {}, context) as Vars);
        if (response.status >= 500 || response.status === 429) {
          const handler = (state.catch ?? []).find((c: StateDef) => c.on === 'any');
          if (!handler) throw new Error(`HTTP ${response.status} from ${state.service}:${url}`);
          frame.state_id = handler.next;
          break;
        }
        const result = projectCapture({ status: response.status, headers: {}, body: response.body }, state.capture ?? {});
        if (state.assign) setPath(frame.vars, state.assign, result);
        log(run, `[ENGINE LOG] ✅ HTTP Call completed. Projected output assigned to '${state.assign}'`);
        frame.state_id = state.next;
        break;
      }

      case 'choice': {
        const rule = (state.rules as StateDef[]).find((r) => evaluate(r.when, context));
        frame.state_id = rule ? rule.next : state.default;
        break;
      }

      case 'assign':
        applyAssign(frame, state, context);
        frame.state_id = state.next;
        break;

      case 'invoke': {
        const target = processOf(run, state.process);
        if (!target) {
          throw new Error(`Process '${state.process}' invoked by state '${frame.state_id}' not found`);
        }
        frame.state_id = state.next;
        const vars = clone(target.vars ?? {});
        if (state.input) vars.input = resolveDict(state.input, context);
        log(run, `[ENGINE LOG] 🔀 Invoking sub-process stack frame '${state.process}' (Start state: '${target.start}')`);
        run.frames.push({ process_id: state.process, state_id: target.start, vars, invoker: state });
        break;
      }

      case 'wait':
        // The real executor sleeps (durably) here; the mock moves straight on.
        frame.state_id = state.next;
        break;

      case 'end': {
        const returned = state.return !== undefined && state.return !== null ? resolveDict(state.return, context) : null;
        const popped = run.frames.pop()!;
        const parent = run.frames[run.frames.length - 1];
        if (!parent) {
          run.status = 'COMPLETED';
          run.result = { status: state.status, outcome: state.outcome, return: returned };
          return;
        }
        const invoker = popped.invoker;
        if (invoker) {
          if (invoker.assign && returned !== null) setPath(parent.vars, invoker.assign, returned);
          const handler = (invoker.catch ?? []).find((c: StateDef) => c.on === state.outcome || c.on === 'any');
          if (handler) parent.state_id = handler.next;
        }
        break;
      }

      default:
        throw new Error(`Unsupported state type '${state.type}' at ${frame.process_id}.${frame.state_id}`);
    }
  }
}

function awaitInput(run: MockRun, frame: Frame, state: StateDef, context: Vars): void {
  const schema = clone(state.schema ?? {}) as Vars;
  let options: unknown = null;
  if (schema.options_from) options = resolvePath(context, schema.options_from as string);
  else if (schema.options) options = schema.options;

  let timeoutMs: number | null = null;
  if (state.timeout && 'after' in state.timeout) {
    const after = resolveDict(state.timeout.after, context);
    if (typeof after !== 'string') throw new Error("Timeout 'after' must resolve to a valid duration string");
    timeoutMs = parseDuration(after);
  }
  if (options !== null) schema.options = options;

  const token = `tkn_${run.stepCounter}`;
  run.awaiting = {
    token,
    prompt: interpolate(state.prompt ?? '', context),
    schema: schema as unknown as AwaitingInput['schema'],
    options,
    timeout_seconds: timeoutMs !== null ? timeoutMs / 1000 : null,
    state_id: frame.state_id,
    state_type: 'InputState'
  };

  if (timeoutMs !== null && timeoutMs <= MAX_TIMER_MS) {
    run.timeoutHandle = setTimeout(() => {
      if (run.awaiting?.token !== token) return;
      run.awaiting = null;
      if (!state.timeout.next) {
        fail(run, `Timeout triggered without 'next' route in state '${frame.state_id}'`);
        return;
      }
      frame.state_id = state.timeout.next;
      advance(run);
    }, timeoutMs);
  }
}

function applyAssign(frame: Frame, state: StateDef, context: Vars): void {
  for (const [key, spec] of Object.entries(state.set as Vars)) {
    if (!spec || typeof spec !== 'object' || Array.isArray(spec) || !('op' in spec)) {
      setPath(frame.vars, key, resolveDict(spec, context));
      continue;
    }
    const v = spec as StateDef;
    switch (v.op) {
      case 'add': {
        const a = resolvePath(context, v.path ?? '');
        const b = 'value_path' in v ? resolvePath(context, v.value_path) : (v.value ?? null);
        if (a !== null && b !== null) setPath(frame.vars, key, (a as number) + (b as number));
        break;
      }
      case 'now_plus': {
        const dur = v.value_path ? resolvePath(context, v.value_path) : null;
        if (dur) setPath(frame.vars, key, isoNaive(new Date(Date.now() + parseDuration(String(dur)))));
        break;
      }
      case 'date_add':
      case 'date_subtract':
        setPath(frame.vars, key, applyDateMath(resolvePath(context, v.path ?? ''), v.value, v.op === 'date_add' ? 'add' : 'subtract'));
        break;
      case 'date_before':
      case 'before_now':
      case 'is_true':
      case 'is_false':
      case 'eq':
      case 'lt':
      case 'gt':
        setPath(frame.vars, key, evaluate(v, context));
        break;
      // Any other op (e.g. date_diff_greater_than) is silently ignored, as in interpreter.py.
    }
  }
}

function projectCapture(full: Vars, spec: Vars): Vars {
  const result: Vars = {};
  for (const [key, rule] of Object.entries(spec)) {
    if (typeof rule === 'string') {
      result[key] = resolvePath(full, rule);
    } else if (rule && typeof rule === 'object') {
      const r = rule as StateDef;
      const source = resolvePath(full, r.from ?? '');
      if (Array.isArray(source)) {
        let projected = source.map((item) =>
          item && typeof item === 'object' && r.pick
            ? Object.fromEntries((r.pick as string[]).map((p) => [p, (item as Vars)[p] ?? null]))
            : item
        );
        if (r.max_items) projected = projected.slice(0, r.max_items);
        result[key] = projected;
      } else if (typeof source === 'string' && 'max_length' in r) {
        result[key] = source.slice(0, r.max_length);
      } else {
        result[key] = source;
      }
    }
  }
  return result;
}

// --- submit_input: validator + value processing from interpreter.py ---

function optionValue(opt: unknown, valueKey: string): unknown {
  if (opt && typeof opt === 'object') {
    const o = opt as Vars;
    return o[valueKey] ?? o.uprn ?? o.id ?? o.value ?? null;
  }
  return opt;
}

function sameValue(a: unknown, b: unknown): boolean {
  return a === b || (typeof a === 'object' && JSON.stringify(a) === JSON.stringify(b));
}

function validate(awaiting: AwaitingInput, token: string, val: unknown): void {
  if (token !== awaiting.token) throw new MockInputError(`Token mismatch. Expected ${awaiting.token}`);
  const schema = awaiting.schema as unknown as Vars;
  const kind = schema.kind;

  if (kind === 'boolean' && typeof val !== 'boolean') {
    throw new MockInputError(`Expected boolean, received ${typeof val}`);
  }
  if (kind === 'string') {
    if (typeof val !== 'string') throw new MockInputError(`Expected string, received ${typeof val}`);
    if (schema.pattern && !new RegExp(`^(?:${schema.pattern})`).test(val)) {
      throw new MockInputError((schema.invalid_message as string) ?? 'Invalid format');
    }
  }
  if (kind === 'select_one' || kind === 'select_many') {
    const options = ((schema.options as unknown[]) ?? (awaiting.options as unknown[]) ?? []) as unknown[];
    const validValues = options.map((opt) => optionValue(opt, (schema.value_key as string) ?? 'value'));
    const isValid = (item: unknown) =>
      (Number.isInteger(item) && (item as number) >= 1 && (item as number) <= options.length) ||
      validValues.some((v) => sameValue(v, item)) ||
      options.some((o) => sameValue(o, item));

    if (kind === 'select_one' && !isValid(val)) {
      throw new MockInputError(`Invalid selection: '${String(val)}'. Please select a valid option.`);
    }
    if (kind === 'select_many') {
      if (!Array.isArray(val)) throw new MockInputError('Expected list of values for select_many');
      const bad = val.find((item) => !isValid(item));
      if (bad !== undefined) throw new MockInputError(`Invalid item '${String(bad)}' in selection list`);
    }
  }
  if (kind === 'file_ref') {
    const file = val as Vars | null;
    if (!file || typeof file !== 'object' || 'error' in file) {
      throw new MockInputError('Invalid file upload. Please use the upload button.');
    }
    if (!file.ref || Number(file.bytes ?? 0) <= 0) {
      throw new MockInputError('File payload missing valid reference or size.');
    }
  }
}

function normaliseValue(schema: Vars, options: unknown[], raw: unknown): unknown {
  let val = raw;
  const kind = schema.kind;
  const valueKey = schema.value_key as string | undefined;

  if (kind === 'select_one' && Number.isInteger(val)) {
    const opt = options[(val as number) - 1];
    if (opt !== undefined) {
      if (opt && typeof opt === 'object') {
        val = ['uprn', 'single_line', 'address_line_1'].includes(valueKey ?? '')
          ? opt
          : ((opt as Vars)[valueKey ?? 'value'] ?? (opt as Vars).uprn ?? (opt as Vars).id ?? opt);
      } else {
        val = opt;
      }
    }
  } else if (kind === 'select_many' && Array.isArray(val)) {
    val = val.map((item) => {
      const opt = Number.isInteger(item) ? options[item - 1] : undefined;
      if (opt === undefined) return item;
      return opt && typeof opt === 'object' ? ((opt as Vars)[valueKey ?? 'value'] ?? (opt as Vars).id ?? opt) : opt;
    });
  }

  if (typeof val === 'string') {
    if (schema.normalise === 'upper_trim') val = val.trim().toUpperCase();
    else if (schema.normalise === 'trim') val = val.trim();
    else if (schema.normalise === 'lower_trim') val = val.trim().toLowerCase();
    if ((val as string).trim() === '') val = schema.default ?? null;
  }
  return val;
}

export function submitInput(run: MockRun, token: string, value: unknown): void {
  if (!run.awaiting) throw new MockInputError('Not awaiting input');
  validate(run.awaiting, token, value);

  const frame = run.frames[run.frames.length - 1];
  const state = processOf(run, frame.process_id).states[frame.state_id];
  const schema = run.awaiting.schema as unknown as Vars;
  const options = ((run.awaiting.options as unknown[]) ?? (schema.options as unknown[]) ?? []) as unknown[];

  if (run.timeoutHandle) clearTimeout(run.timeoutHandle);
  run.timeoutHandle = null;
  run.awaiting = null;

  if (state.assign) setPath(frame.vars, state.assign, normaliseValue(schema, options, value));
  frame.state_id = state.next;
  advance(run);
}
