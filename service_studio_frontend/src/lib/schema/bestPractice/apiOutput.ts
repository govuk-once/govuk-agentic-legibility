import { z } from 'zod';
import { inputStateSchema } from '$lib/schema/workflow/input-state';
import { outputStateSchema } from '$lib/schema/workflow/states';
import { stateSchema } from '$lib/schame/workflow/workflow';


export const outputInputSchema = z.array(stateSchema).superRefine((items, ctx) => {
	for (let i = 0; i < items.length; i++) {
		const next = items[i+1];
		const current = items[i];

		if (current.state_type === 'api_call' && next.state_type != 'output') {
			ctx.addIssue({
				code: z.ZodIssueCode.custom,
				path: [i],
				mesage: `${current.state_type} should be preceeded by an output`,
			});
		}
	}
	});
