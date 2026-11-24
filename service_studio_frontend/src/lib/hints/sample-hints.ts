import type { CanvasHint } from './hint-nodes';

/*
	Sample best practice hints, shown when Show hints is ticked. They are not worked out from the form yet. They are
	written for the states of one example form, so the design of a hint on the canvas can be seen and reviewed
	before the checks that find hints are built. A form with no sample hints shows none.
*/

// The sample hints for each example form, by the process id of the form.
export const sampleHints: Record<string, CanvasHint[]> = {
	'2026_bft_crrf_additional_trainer_information_with_modules': [
		{
			stateIds: ['step_1', 'step_2', 'step_3'],
			title: 'Three questions in a row',
			advice: 'Break them up with a message so the form feels shorter.'
		},
		{
			stateIds: ['declaration_declined'],
			title: 'Ends the form early',
			advice: 'This route finishes straight away. Check that is what you want.'
		}
	]
};
