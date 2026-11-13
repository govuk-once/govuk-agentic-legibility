import { z } from 'zod';
import { apiCallStateSchema } from './api-call-state';
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
	4. The key that names the kind of state is state_type, as in the document. The key type is accepted when a
	   file is read, because the executor reads it and the form files use it. See acceptTypeAlias.
*/

// Any one of the eight states, picked by its state_type. The state_type decides which keys are allowed.
export const stateUnionSchema = z.discriminatedUnion('state_type', [
	inputStateSchema,
	outputStateSchema,
	apiCallStateSchema,
	choiceStateSchema,
	assignStateSchema,
	invokeStateSchema,
	waitStateSchema,
	endStateSchema
]);

/**
 * Lets a file name the kind of state with the key type as well as state_type. The document and the published schema
 * call the key state_type. The executor reads either, and the form files and the older executor examples use type, so
 * both are accepted when a file is read. The state that comes out always has state_type, so a workflow that is saved
 * again says state_type. A state with both keys is passed on as it is, and the check reports the extra key.
 */
function acceptTypeAlias(value: unknown): unknown {
	if (value === null || typeof value !== 'object' || Array.isArray(value)) return value;
	if (!('type' in value) || 'state_type' in value) return value;

	const { type, ...rest } = value as Record<string, unknown>;
	return { state_type: type, ...rest };
}

// A state as it is read from a file, with the alias accepted.
export const stateSchema = z.preprocess(acceptTypeAlias, stateUnionSchema);

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
