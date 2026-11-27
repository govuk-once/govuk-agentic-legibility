import { describeDuration } from '$lib/process-graph/describe-value';
import type { WaitState } from '$lib/schema/workflow/states';
import { durationSchema, variablePathSchema } from '$lib/schema/workflow/primitives';
import type { WorkingWait } from '$lib/schema/workflow/working-process';
import type { StepValuesResult } from './step-values';

/*
	The one value of a wait step: how long it waits. It is written as a duration such as PT30M, or as the name of a
	saved value that holds the duration, such as wait_time.
*/

// The id of the duration field, which a problem names so the error summary can link to it.
export const waitDurationField = 'wait-duration';

/**
 * Writes the duration of a wait as it is typed: the duration itself, or the name of the saved value that holds it.
 */
export function waitDurationText(state: WorkingWait): string {
	return typeof state.duration === 'string' ? state.duration : state.duration.$;
}

/**
 * Reads the typed duration into the wait. Text that is a duration is written as one, and text that is the name of a
 * saved value is written as a reference to it.
 */
export function waitWithDuration(state: WorkingWait, text: string): StepValuesResult<WorkingWait> {
	const typed = text.trim();
	let duration: WaitState['duration'] | undefined;
	if (durationSchema.safeParse(typed).success) duration = typed;
	else if (variablePathSchema.safeParse(typed).success) duration = { $: typed };

	if (!duration) {
		return {
			ok: false,
			problems: [{ field: waitDurationField, message: 'Enter a duration such as PT30M, or the name of a saved value such as wait_time' }]
		};
	}
	return { ok: true, state: { ...state, duration } };
}

/**
 * Writes a typed duration in words, such as "30 minutes" for PT30M, so the panel can say how long the wait is. Text
 * that is not a duration, such as the name of a saved value, gives nothing.
 */
export function typedDurationInWords(text: string): string | undefined {
	const typed = text.trim();
	return durationSchema.safeParse(typed).success ? describeDuration(typed) : undefined;
}
