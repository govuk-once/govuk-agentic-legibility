import type { Process, State } from '$lib/schema/workflow/process';
import type { Workflow } from '$lib/schema/workflow/workflow';

/*
	The shapes the editor works with while a journey is being built. A saved process needs every state except an
	end to continue somewhere, but a step that has just been added to the canvas may not be joined to anything yet,
	and a decision may have lost the state one of its ways out led to. So the editor lets those keys be missing and
	leaves everything else about a state as it is in a saved process.

	1. A saved process can always be used where an editing one is expected, because it has every key that an
	   editing one may have.
	2. The strict shape in process.ts is unchanged. It is what a journey must match when it is checked before it is
	   saved or passed on, and that is where a missing key is reported.
*/

// A state type that has a next key is given the same key as optional. A state type without one is left alone.
type WithOptionalNext<Each> = Each extends { next: string } ? Omit<Each, 'next'> & { next?: string } : Each;

// A decision is given its default as optional, and the next of each of its rules as optional, so a way out can be
// left leading nowhere while its rule and its place in the order are kept. Any other state type is left alone.
type WithOptionalWaysOut<Each> = Each extends { rules: Array<infer Rule>; default: string }
	? Omit<Each, 'rules' | 'default'> & { rules: Array<WithOptionalNext<Rule>>; default?: string }
	: Each;

// Any one of the eight states, as the editor holds it.
export type WorkingState = WithOptionalWaysOut<WithOptionalNext<State>>;

// The kinds of state the editors work on one at a time, as the editor holds them. Each is named once here so every
// file that edits one kind uses the same name.
export type WorkingInput = Extract<WorkingState, { state_type: 'input' }>;
export type WorkingChoice = Extract<WorkingState, { state_type: 'choice' }>;
export type WorkingApiCall = Extract<WorkingState, { state_type: 'api_call' }>;
export type WorkingAssign = Extract<WorkingState, { state_type: 'assign' }>;
export type WorkingWait = Extract<WorkingState, { state_type: 'wait' }>;

// A process as the editor holds it, where a state may not say where it continues to yet. The start may be missing
// too, which is how the process is held after the state it started at is taken out and before a new one is chosen.
export type WorkingProcess = Omit<Process, 'states' | 'start'> & { start?: string; states: Record<string, WorkingState> };

// A workflow as the editor holds it: the manifest as it was saved, and every process in its editing shape.
export type WorkingWorkflow = Omit<Workflow, 'processes'> & { processes: Record<string, WorkingProcess> };
