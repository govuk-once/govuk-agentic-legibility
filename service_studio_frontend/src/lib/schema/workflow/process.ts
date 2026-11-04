import { z } from 'zod';
import { callStateSchema } from './call-state';
import { choiceStateSchema } from './choice-state';
import { inputStateSchema } from './input-state';
import { invokeStateSchema } from './invoke-state';
import { metadataSchema, stateRefSchema, variablePathSchema, versionSchema } from './primitives';
import { assignStateSchema, endStateSchema, outputStateSchema, waitStateSchema } from './states';

/*
	The process file from section 1.6 of the unified class structure document. Each process is saved
	in its own file and the workflow manifest lists them, so a process carries its own process_id and
	version.

	1. parent_process is not accepted. The document lists it, but a sub process is found from the
	   invoke state that runs it, so the key would only repeat that and could disagree with it.
	2. vars is required because every example process has it, even though the document does not say.
	   A process with no variables writes an empty object.
	3. The document says window is a map holding a start and an end date, but names no keys. The keys
	   start and end are assumed, and a date or a date and time are both accepted.
*/

// Any one of the eight states, picked by its type. The type decides which keys are allowed.
export const stateSchema = z.discriminatedUnion('type', [
	inputStateSchema,
	outputStateSchema,
	callStateSchema,
	choiceStateSchema,
	assignStateSchema,
	invokeStateSchema,
	waitStateSchema,
	endStateSchema
]);

// The dates between which a process is open, used for services that only run for a set period.
const windowSchema = z.strictObject({
	start: z.union([z.iso.date(), z.iso.datetime()]),
	end: z.union([z.iso.date(), z.iso.datetime()])
});

// The states of a process, keyed by their names. A process with no states could not start or end.
const statesSchema = z
	.record(stateRefSchema, stateSchema)
	.refine((states) => Object.keys(states).length > 0, { message: 'A process needs at least one state' });

export const processSchema = z.strictObject({
	process_id: z.string().min(1),
	version: versionSchema,
	metadata: metadataSchema.optional(),
	start: stateRefSchema,
	vars: z.record(variablePathSchema, z.json()),
	states: statesSchema,
	performer: z.string().min(1).optional(),
	source: z.array(z.url()).optional(),
	window: windowSchema.nullable().optional()
});

export type State = z.infer<typeof stateSchema>;
export type Process = z.infer<typeof processSchema>;
