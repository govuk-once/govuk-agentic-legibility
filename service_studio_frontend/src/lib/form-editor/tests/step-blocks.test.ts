import { describe, expect, it } from 'vitest';
import { addModule } from '$lib/modules/add-module';
import { withChoiceTargets, withNext } from '$lib/schema/workflow/edit-state';
import { reachableInOrder } from '$lib/schema/workflow/journey-order';
import { canMoveEarlier, canMoveLater, moveEarlier, moveLater } from '$lib/schema/workflow/move-state';
import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
import { formStepBlock } from '$lib/form-editor/step-blocks';

const message = (text: string): WorkingState => ({ state_type: 'output', channel: 'transcript', message: text });

// Gives a state a new next, or a decision a new default, as a person joining the steps would.
function join(process: WorkingProcess, code: string, target: string): WorkingProcess {
	const state = process.states[code];
	const joined = state.state_type === 'choice' ? withChoiceTargets(state, state.rules.map((rule) => rule.next ?? ''), target) : withNext(state, target);
	return { ...process, states: { ...process.states, [code]: joined } };
}

// A message, then a Many answers module, then another message: "Before", the four states of the loop, "After".
function manyAnswersJourney(): WorkingProcess {
	const base: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'before', vars: {}, states: { before: message('Before'), after: message('After') } };
	const { process } = addModule(base, 'many_answers');
	return join(join(process, 'before', 'many_answers_ask'), 'many_answers_again', 'after');
}

describe('moving a module up or down the list of steps', () => {
	it('moves every state of the module together when the step after it moves up', () => {
		const moved = moveEarlier(manyAnswersJourney(), 'after', formStepBlock);
		expect(reachableInOrder(moved)).toEqual(['before', 'after', 'many_answers_ask', 'many_answers_keep', 'many_answers_more', 'many_answers_again']);
	});

	it('keeps the loop inside the module going back to its own question', () => {
		const moved = moveEarlier(manyAnswersJourney(), 'after', formStepBlock);
		const again = moved.states.many_answers_again;
		expect(again.state_type === 'choice' && again.rules[0].next).toBe('many_answers_ask');
	});

	it('moves the whole module whichever of its states is moved, and never leaves one behind', () => {
		const journey = manyAnswersJourney();
		const byQuestion = moveLater(journey, 'many_answers_ask', formStepBlock);
		const byLastQuestion = moveLater(journey, 'many_answers_more', formStepBlock);
		expect(byLastQuestion).toEqual(byQuestion);
		expect(reachableInOrder(byQuestion)).toEqual(['before', 'after', 'many_answers_ask', 'many_answers_keep', 'many_answers_more', 'many_answers_again']);
	});

	it('does not move a module that branches, or let a step move past it', () => {
		const base: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'before', vars: {}, states: { before: message('Before') } };
		const { process } = addModule(base, 'boolean_decision');
		const joined = join(process, 'before', 'boolean_decision_ask');

		expect(canMoveEarlier(joined, 'boolean_decision_ask', formStepBlock)).toBe(false);
		expect(canMoveLater(joined, 'boolean_decision_ask', formStepBlock)).toBe(false);
		expect(canMoveLater(joined, 'before', formStepBlock)).toBe(false);
	});

	it('moves a module of one state like a step', () => {
		const base: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'before', vars: {}, states: { before: message('Before') } };
		const { process, first } = addModule(base, 'message');
		const joined = join(process, 'before', first);
		expect(reachableInOrder(moveEarlier(joined, first, formStepBlock))).toEqual([first, 'before']);
	});
});
