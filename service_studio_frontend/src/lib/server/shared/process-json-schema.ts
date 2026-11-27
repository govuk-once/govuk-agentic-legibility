import { z } from 'zod';
import { processSchema } from '$lib/schema/workflow/process';

// The words that come between the instructions and the schema.
const schemaIntro = 'The JSON you reply with must validate against this JSON Schema:';

// Read from the schema itself, rather than described a second time by hand, so this never drifts out of step with
// processSchema. Bedrock does not support output_config for Claude Sonnet 5 on either of its endpoints, so this is
// the only thing constraining the shape of the response: the instructions cover judgement and content, and this
// covers the exact keys, allowed values and formats that the check will use.
const PROCESS_JSON_SCHEMA = JSON.stringify(z.toJSONSchema(processSchema));

/**
 * Ends a set of instructions with the JSON Schema of a process, which makes the whole system prompt. Every kind of
 * draft is one process, so each prompt is finished here in the same way.
 */
export function withProcessSchema(instructions: string): string {
	return `${instructions}\n\n${schemaIntro}\n\n${PROCESS_JSON_SCHEMA}`;
}
