import { z } from 'zod';
import { expressionSchema } from '$lib/schema/workflow/expression';
import { durationOrRefSchema, metadataSchema, stateRefSchema, variablePathSchema } from '$lib/schema/workflow/primitives';

// Each workflow state is represented by a separate schema
import { inputStateSchema } from '$lib/schema/workflow/input-state';
import { apiCallStateSchema } from '$lib/schema/workflow/api-call-state';
import { choiceStateSchema } from '$lib/schema/workflow/choice-state';
import { invokeStateSchema } from '$lib/schema/workflow/invoke-state';
import { endStateSchema } from '$lib/schema/workflow/end-state';
import { assignStateSchema } from '$lib/schema/workflow/assign-state';
import { outputStateSchema } from '$lib/schema/workflow/output-state';
import { waitStateSchema } from '$lib/schema/workflow/wait-state';


/*
	The four simple states from sections 1.8, 1.11, 1.13 and 1.14 of the unified class structure
	document: output, assign, wait and end. Each is a strict object, so a key the document does not
	list is rejected.

	1. Every state accepts an optional name and metadata. The name
	   is the title shown to a person, and the metadata holds notes that only Service Studio reads at this time (future iterations of the executor may use some metadata).
	2. The document does not say which keys are required. A key is required here only when every
	   real example state includes it and the document gives no default for it.
	3. An output on the transcript channel needs a message, and an output on email or sms needs a
	   template, because the document says each channel reads a different one of the two.
	4. The return of an end state is a map of names to expressions, as the document says. A state that hands
	   nothing back leaves the key out, and null is refused.
*/

/**
 * The keys of the BaseState class in section 1.7 of the unified class structure document that every state
 * shares: the optional title and the notes. Each state schema spreads these in, so they are described once.
 * The document names the state type key state_type, as a field of BaseState. Each state gives it its own fixed value,
 * so it is written in each state schema and not here. A file may also say type, which is accepted when it is read.
 * See acceptTypeAlias in process.ts.
 */
export const baseStateFields = {
	name: z.string().min(1).optional(),
	metadata: metadataSchema.optional()
};


export const stateSchema = z.union([
	inputStateSchema,
	outputStateSchema,
	assignStateSchema,
	waitStateSchema,
	endStateSchema,
	apiCallStateSchema,
	choiceStateSchema,
	invokeStateSchema,
]);


