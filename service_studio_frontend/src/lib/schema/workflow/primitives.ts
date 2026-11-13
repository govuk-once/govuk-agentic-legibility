import { z } from 'zod';

/*
	Shared building blocks for the unified workflow schema (Workflow/0.2). Conditions, expressions and
	states all reuse these, so the rules for a path, a reference and a duration live in one place.
*/

/**
 * A dot separated path into the runtime variables, for example "applicant.date_of_birth". The
 * pattern is checked here so a typo such as a trailing dot or a space fails validation at design
 * time instead of surfacing when the executor runs the workflow. The special path "__now__" also
 * matches, because the executor resolves it to the current time.
 */
export const variablePathSchema = z
	.string()
	.regex(
		/^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)*$/,
		'Must be a dot separated path such as "applicant.date_of_birth"'
	);

/**
 * An ISO 8601 duration such as "PT30S" or "P14D". Checking the format here stops a plain phrase
 * such as "two days" being saved, which the executor could not read.
 */
export const durationSchema = z.iso.duration();

/**
 * A reference to a variable, written as { "$": "path" }. The executor swaps it for the variable's
 * value at run time. The object is strict so that extra keys fail validation, because the same
 * shape is how an expression tells a reference apart from a plain literal object.
 */
export const dynamicRefSchema = z.strictObject({ $: variablePathSchema });

/**
 * A duration that is either written directly or read from a variable. The wait state and the input
 * timeout both accept either form, so that a service can set its waiting time in one place.
 */
export const durationOrRefSchema = z.union([durationSchema, dynamicRefSchema]);

/**
 * A semantic version such as "0.1.0", used for a workflow and for each process in it. Checking the
 * three numbers means a version can be compared and a mismatch between the manifest and a process
 * file can be spotted.
 */
export const versionSchema = z
	.string()
	.regex(
		/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/,
		'Must be a version such as "0.1.0"'
	);

/**
 * The name of a state inside its own process, used wherever one state points at the next. The
 * check that the name belongs to a real state is made later, once the whole process is known.
 */
export const stateRefSchema = z.string().min(1, 'Give the name of a state');

/**
 * The name of a process, used where one state hands over to another process. The check that the
 * process exists is made later, once every process in the workflow is known.
 */
export const processRefSchema = z.string().min(1, 'Give the name of a process');

// The notes that Service Studio reads and shows as words, so each must be text, or null when it has not been given.
// Every other note is only carried through and is never read here.
export const textNoteKeys = ['description', 'hint_text', 'page_heading', 'guidance_markdown', 'answer_type'] as const;

/**
 * Notes about a workflow, a process or a state, stored as entries of a name and a value. A value can be anything that
 * a JSON file can hold: text, a number, true or false, null, a list or a nested object. The notes carry whatever a
 * form needs to be rebuilt later, such as its position or its answer settings, and Service Studio keeps them exactly
 * as they were loaded. The only values it checks are the notes in textNoteKeys, which it shows as words and so must be
 * text, or null when not given.
 */
export const metadataSchema = z.record(z.string(), z.json()).superRefine((notes, context) => {
	for (const key of textNoteKeys) {
		const note = notes[key];
		if (note !== undefined && note !== null && typeof note !== 'string') {
			context.addIssue({ code: 'custom', path: [key], message: `The note ${key} must be text, because it is shown as words` });
		}
	}
});

export type VariablePath = z.infer<typeof variablePathSchema>;
export type Duration = z.infer<typeof durationSchema>;
export type DynamicRef = z.infer<typeof dynamicRefSchema>;
export type DurationOrRef = z.infer<typeof durationOrRefSchema>;
export type Version = z.infer<typeof versionSchema>;
export type StateRef = z.infer<typeof stateRefSchema>;
export type ProcessRef = z.infer<typeof processRefSchema>;
export type Metadata = z.infer<typeof metadataSchema>;
