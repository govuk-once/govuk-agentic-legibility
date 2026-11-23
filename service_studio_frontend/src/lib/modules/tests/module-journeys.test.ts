import { describe, expect, it } from 'vitest';
import { withNext } from '$lib/schema/workflow/edit-state';
import { journeyErrors } from '$lib/schema/workflow/validate';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { addModule } from '../add-module';
import type { ModuleKey } from '../module-states';

/*
	Forms made only of modules, joined one after another as a person would join them on the canvas, pass the check
	before owner review. These modules bring states a form did not have before modules: a wait, API calls and an end
	that sends the person offline.
*/

/**
 * Builds a form from modules of one state each, in order, joined to a last module that ends the journey. Each
 * state continues to the first state of the module after it, and the journey starts at the first module.
 */
function formOf(keys: ModuleKey[], endsWith: ModuleKey): WorkingProcess {
	let process: WorkingProcess = { process_id: 'modules', version: '0.1.0', start: '', vars: {}, states: {} };
	const firsts: string[] = [];
	for (const key of [...keys, endsWith]) {
		const added = addModule(process, key);
		process = added.process;
		firsts.push(added.first);
	}

	keys.forEach((_, index) => {
		const code = firsts[index];
		process = { ...process, states: { ...process.states, [code]: withNext(process.states[code], firsts[index + 1]) } };
	});
	return { ...process, start: firsts[0] };
}

describe('a form made of modules', () => {
	it('passes the check with a wait and the API calls of Submit', () => {
		expect(journeyErrors(formOf(['start_page', 'wait'], 'submit'))).toEqual([]);
	});

	it('passes the check when it ends by sending the person offline', () => {
		expect(journeyErrors(formOf(['start_page', 'message'], 'information'))).toEqual([]);
	});
});
