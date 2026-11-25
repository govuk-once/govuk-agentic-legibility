import { z } from 'zod';
import { retryPolicySchema, timeoutsSchema } from './api-call-state';
import { durationSchema, metadataSchema, processRefSchema, versionSchema } from './primitives';
import { processSchema } from './process';

/*
	The workflow manifest from sections 1.1 to 1.3 of the unified class structure document, and the
	assembled workflow that joins the manifest to its process files. The manifest is saved as
	workflow_manifest.json and lists the processes, and each process is saved in a file of its own.

	1. The document gives processes as a map of full process definitions. The split files list each
	   process by process_id and version in the manifest instead, so processes here is a list of
	   those references.
	2. id must have at least two parts joined by dots, such as "dwp.maternity_allowance_ma1_claim",
	   because the document calls it a namespaced identifier. The document gives no stricter format.
	3. As with the states, a key is required when every example manifest includes it and the document
	   gives no default. That makes executor and defaults required, and also search_attributes.
	4. defaults is keyed by activity type. The document calls the key http_call in section 1.1 and
	   api_call in section 1.9, so api_call is used, to match the name of the state. notify is not a
	   state type, so it is accepted and not used until the executor team explains it.
	5. workflow_id is a number or text, as the document says, because the two examples differ.
	6. The document gives the schema value as "Workflow/0.2", and the published schema accepts "Workflow/x.y" with
	   any two numbers. The older value "sfsm/0.2" is refused. A draft that Service Studio writes uses "Workflow/0.2".
	7. A null means the same as a key that is not there: nothing has been given yet. A form made from an existing form
	   has no owner, and may have no contact, so the owner and the contact may be missing or null, and so may the
	   optional manifest and executor keys. Nothing here changes a null to a missing key, so a workflow that is saved
	   again says what it said when it was loaded. Asking for a real owner and contact is left to the policy review,
	   before a workflow is published.
*/

// The schema value of a manifest is the word Workflow, a slash and two numbers, such as Workflow/0.2.
const schemaValueSchema = z.string().regex(/^Workflow\/\d+\.\d+$/, 'Must be a schema value such as "Workflow/0.2"');

// The schema value that Service Studio writes into a new draft.
export const currentSchemaVersion = 'Workflow/0.2';

// How the executor runs and names each execution of the workflow.
const executorSchema = z.strictObject({
	workflow_id_template: z.string().min(1),
	id_reuse_policy: z.enum(['reject_duplicate', 'allow_duplicate', 'terminate_existing']),
	run_timeout: durationSchema,
	continue_as_new: z.record(z.string(), z.string()).nullish(),
	search_attributes: z.record(z.string(), z.json())
});

// The timeouts and retry policy that a type of activity uses unless a state overrides them.
const activityDefaultsSchema = z.strictObject({
	timeouts: timeoutsSchema.optional(),
	retry: retryPolicySchema.optional()
});

// One entry in the manifest's list of processes. It points at a process file by id and version.
const processReferenceSchema = z.strictObject({
	process_id: processRefSchema,
	version: versionSchema
});

export const manifestSchema = z.strictObject({
	workflow_id: z.union([z.string().min(1), z.number().int()]),
	schema: schemaValueSchema,
	id: z.string().regex(/^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$/, 'Must be a namespaced id such as "dwp.maternity_allowance"'),
	version: versionSchema,
	owner: z.string().min(1).nullish(),
	contact: z.email().nullish(),
	description: z.string(),
	state: z.enum(['draft', 'live', 'deprecated', 'retired']),
	metadata: metadataSchema.nullish(),
	entry: processRefSchema,
	executor: executorSchema,
	defaults: z.strictObject({
		api_call: activityDefaultsSchema.nullish(),
		notify: activityDefaultsSchema.nullish()
	}),
	processes: z.array(processReferenceSchema).min(1, 'List at least one process')
});

// The manifest together with every process file it lists, keyed by process_id. This is the one
// object that the editor works on and that the checks across processes read.
export const workflowSchema = z.strictObject({
	manifest: manifestSchema,
	processes: z.record(processRefSchema, processSchema)
});

export type Manifest = z.infer<typeof manifestSchema>;
export type Workflow = z.infer<typeof workflowSchema>;
