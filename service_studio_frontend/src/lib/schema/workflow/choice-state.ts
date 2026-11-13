import { z } from 'zod';
import { conditionSchema } from './condition';
import { baseStateFields } from './states';
import { stateRefSchema } from './primitives';

/*
	The choice state from sections 1.10 and 2.4 of the unified class structure document. It is the
	diamond on the graph: it checks its rules in order and takes the first one that matches.

	1. The document gives rules a minimum of one and says the default is the fallback, but does not
	   say whether the default is required. It is required here, because every choice in the example
	   workflows has one and a choice with no match would leave the workflow stuck.
*/

// One rule: when the condition is true, move to the named state.
export const choiceRuleSchema = z.strictObject({
	when: conditionSchema,
	next: stateRefSchema
});

// Checks the rules from the first to the last, then falls back to the default state.
export const choiceStateSchema = z.strictObject({
	state_type: z.literal('choice'),
	...baseStateFields,
	rules: z.array(choiceRuleSchema).min(1, 'Give at least one rule'),
	default: stateRefSchema
});

export type ChoiceRule = z.infer<typeof choiceRuleSchema>;
export type ChoiceState = z.infer<typeof choiceStateSchema>;
