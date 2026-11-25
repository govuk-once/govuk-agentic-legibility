import { durationAsAmount, durationFrom, durationInSeconds, type TimeUnit } from './durations';
import { placeholderApiCallDefaults } from './placeholders';
import type { Manifest } from './workflow';
import type { WorkingProcess } from './working-process';

/*
	The settings for a whole workflow that the technical review sets: how long one run may last, and the time limit
	and retries every API call uses unless a call sets its own. They live in the manifest, as executor.run_timeout and
	defaults.api_call. Each is held as the text typed into its field, so a page can show what was typed even when it is
	not a number, and is only written to the manifest once it passes its check.
*/

export interface WorkflowSettings {
	runTimeout: string;
	runTimeoutUnit: TimeUnit;
	// How many seconds a call may take before it is stopped, kept as timeouts.start_to_close.
	callTimeout: string;
	// How many times a call is tried in all, kept as retry.max_attempts.
	attempts: string;
	// How many seconds to wait before trying a call again, kept as retry.initial_interval.
	pauseBetween: string;
}

export type WorkflowSettingsField = keyof WorkflowSettings;

export interface WorkflowSettingsProblem {
	field: WorkflowSettingsField;
	message: string;
}

// Reads a duration as a whole number of seconds for a field, or gives an empty field when it cannot be read.
function secondsField(duration: string | undefined): string {
	const seconds = duration === undefined ? undefined : durationInSeconds(duration);
	return seconds === undefined ? '' : String(seconds);
}

/**
 * Reads the settings from a manifest. A manifest with no API call defaults yet shows the placeholder defaults, which
 * are what every call uses until the review sets its own.
 */
export function workflowSettingsOf(manifest: Manifest): WorkflowSettings {
	const runTimeout = durationAsAmount(manifest.executor.run_timeout);
	const callDefaults = manifest.defaults.api_call;
	const timeouts = callDefaults?.timeouts ?? placeholderApiCallDefaults.timeouts;
	const retry = callDefaults?.retry ?? placeholderApiCallDefaults.retry;
	return {
		runTimeout: runTimeout ? String(runTimeout.amount) : '',
		runTimeoutUnit: runTimeout?.unit ?? 'days',
		callTimeout: secondsField(timeouts.start_to_close),
		attempts: retry.max_attempts === undefined ? '' : String(retry.max_attempts),
		pauseBetween: secondsField(retry.initial_interval)
	};
}

/**
 * Writes the settings into a copy of a manifest. Every other executor setting and every other part of the call
 * defaults is kept. A call default that was never set starts from the placeholder, so the retry policy written is
 * always complete.
 */
export function withWorkflowSettings(manifest: Manifest, settings: WorkflowSettings): Manifest {
	const callDefaults = manifest.defaults.api_call;
	return {
		...manifest,
		executor: { ...manifest.executor, run_timeout: durationFrom(Number(settings.runTimeout), settings.runTimeoutUnit) },
		defaults: {
			...manifest.defaults,
			api_call: {
				...callDefaults,
				timeouts: {
					...(callDefaults?.timeouts ?? placeholderApiCallDefaults.timeouts),
					start_to_close: durationFrom(Number(settings.callTimeout), 'seconds')
				},
				retry: {
					...(callDefaults?.retry ?? placeholderApiCallDefaults.retry),
					max_attempts: Number(settings.attempts),
					initial_interval: durationFrom(Number(settings.pauseBetween), 'seconds')
				}
			}
		}
	};
}

// Whether a field holds a whole number of at least the smallest value it may have.
function isWholeNumber(text: string, smallest: number): boolean {
	return /^\d+$/.test(text.trim()) && Number(text) >= smallest;
}

/**
 * Lists what must be put right before the settings can be saved, in the order the fields are shown. Every value is a
 * whole number. A run and a call must be given some time, and a call is tried at least once. The pause may be none.
 */
export function workflowSettingsProblems(settings: WorkflowSettings): WorkflowSettingsProblem[] {
	const problems: WorkflowSettingsProblem[] = [];
	if (!isWholeNumber(settings.runTimeout, 1)) {
		problems.push({ field: 'runTimeout', message: 'Enter how long a run can last, as a whole number of 1 or more' });
	}
	if (!isWholeNumber(settings.callTimeout, 1)) {
		problems.push({ field: 'callTimeout', message: 'Enter the API call timeout in seconds, as a whole number of 1 or more' });
	}
	if (!isWholeNumber(settings.attempts, 1)) {
		problems.push({ field: 'attempts', message: 'Enter how many times an API call is tried, as a whole number of 1 or more' });
	}
	if (!isWholeNumber(settings.pauseBetween, 0)) {
		problems.push({ field: 'pauseBetween', message: 'Enter the pause between tries in seconds, as a whole number' });
	}
	return problems;
}

/**
 * Finds the longest wait in a process whose time is written in the file, so a page can say whether a run is allowed
 * long enough for it. A wait whose time is held in a variable is only known when the journey runs, so it is left out.
 */
export function longestWait(process: WorkingProcess): { code: string; seconds: number } | undefined {
	let longest: { code: string; seconds: number } | undefined;
	for (const [code, state] of Object.entries(process.states)) {
		if (state.state_type !== 'wait' || typeof state.duration !== 'string') continue;
		const seconds = durationInSeconds(state.duration);
		if (seconds !== undefined && seconds > (longest?.seconds ?? -1)) longest = { code, seconds };
	}
	return longest;
}
