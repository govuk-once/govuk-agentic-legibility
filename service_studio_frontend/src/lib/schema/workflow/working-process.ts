import type { Process, State } from './process';
import type { Workflow } from './workflow';

/*
	The shapes the editor works with while a journey is being built. A saved process needs every state except an
	end to continue somewhere, but a step that has just been added to the canvas may not be joined to anything yet.
	So the editor lets that one key be missing and leaves everything else about a state as it is in a saved process.

	1. A saved process can always be used where an editing one is expected, because it has every key that an
	   editing one may have.
	2. The strict shape in process.ts is unchanged. It is what a journey must match when it is checked before it is
	   saved or passed on, and that is where a missing next is reported.
*/

// A state type that has a next key is given the same key as optional. A state type without one is left alone.
type WithOptionalNext<Each> = Each extends { next: string } ? Omit<Each, 'next'> & { next?: string } : Each;

// Any one of the eight states, as the editor holds it.
export type WorkingState = WithOptionalNext<State>;

// A process as the editor holds it, where any state that continues to a single next state may not have one yet.
export type WorkingProcess = Omit<Process, 'states'> & { states: Record<string, WorkingState> };

// A workflow as the editor holds it: the manifest as it was saved, and every process in its editing shape.
export type WorkingWorkflow = Omit<Workflow, 'processes'> & { processes: Record<string, WorkingProcess> };
