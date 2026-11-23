import type { InputState } from '$lib/schema/workflow/input-state';
import {
	placeholderAnswerVariable,
	placeholderFailedEnd,
	placeholderInput,
	placeholderOutput,
	placeholderWaitDuration,
	unconnectedApiCallDetails
} from '$lib/schema/workflow/placeholders';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import type { AnswerFormatKey } from './answer-formats';
import type { ModuleIconName } from './ModuleIcon.svelte';

/*
	The states each module adds to a journey. The flows come from the executor team, and the words are placeholders
	that the person replaces once the module is on the canvas.

	1. Every state has a short title, so its box on the graph is readable before the person writes their own.
	2. A module is built by a function rather than written out as fixed data, because the same module can be added
	   to a journey more than once. The function is given a way to turn each part of the module, such as "ask" or
	   "decide", into the code of a state, and the editor makes sure every code is unique in the journey. The
	   variable an input saves its answer in is named after the code of its state, so it is unique as well.
	3. A route that leaves the module, such as the routes out of a decision, is left loose. The person joins it to
	   the rest of the journey, and the checks at the end of the editor catch one that is never joined.
	4. The group and group id that tie the states of a module together are added when the module is dropped onto
	   the canvas, not here.
	5. The basic shapes in the menu add a single state of their own and are not listed here.
*/

// The keys of the basic shapes, which are not modules.
type BasicKey = 'start' | 'input' | 'output' | 'decision' | 'end';

// The key of every module in the menu that adds states.
export type ModuleKey = Exclude<ModuleIconName, BasicKey>;

// Turns the name of a part of a module into the code of its state in the journey.
export type PartCode = (part: string) => string;

/**
 * The states a module adds, keyed by their codes, and the code of the state the module begins at, which is where a
 * route from the rest of the journey joins it.
 */
export interface ModuleStates {
	first: string;
	states: Record<string, WorkingState>;
}

export interface ModuleDefinition {
	build: (code: PartCode) => ModuleStates;
	// Set on a decision module whose question offers options, so that adding an option to the question also adds a
	// route for it to the decision. It is read by the editor, so a new module of this kind only needs this setting.
	addsRoutesForOptions?: boolean;
	// The formats the typed question of the module can be checked against, offered on its card. A module without
	// this offers no formats.
	answerFormats?: AnswerFormatKey[];
}

// Placeholder options for a question where the person chooses. Each value is made once and never changes, and only
// the label is written by the person, so a decision that tests a value keeps working while the label is edited.
function placeholderOptions(count: number) {
	return Array.from({ length: count }, (_, index) => ({ value: `option_${index + 1}`, label: `Option ${index + 1}` }));
}

// An input with a title and a placeholder question that saves its answer in a variable named after its code.
function input(code: string, name: string, schema: InputState['schema'] = { kind: 'string' }, prompt = ''): LinkedState {
	return { state_type: 'input', name, ...placeholderInput(code, prompt), schema };
}

// A state that continues to one next state, so it can sit anywhere in a chain. A decision and an end cannot.
type LinkedState = Exclude<WorkingState, { state_type: 'choice' | 'end' }>;

// A message shown to the person, with a title and placeholder words unless some are given.
function output(name: string, message = ''): LinkedState {
	return { state_type: 'output', name, ...placeholderOutput(message) };
}

/**
 * A module made of one state, which has nothing after it yet. The state is made from the code it is given, so
 * an input can name its answer variable after it.
 */
function single(makeState: (code: string) => WorkingState): ModuleDefinition {
	return {
		build: (code) => {
			const only = code('step');
			return { first: only, states: { [only]: makeState(only) } };
		}
	};
}

/**
 * A module made of states that follow one after another, each continuing to the next. The last has nothing after
 * it yet. Each part is given with the state it makes, in the order they run.
 */
function chain(parts: [part: string, makeState: (code: string) => LinkedState][]): ModuleDefinition {
	return {
		build: (code) => {
			const codes = parts.map(([part]) => code(part));
			const states = Object.fromEntries(
				parts.map(([, makeState], index) => {
					const state = makeState(codes[index]);
					const next = codes[index + 1];
					return [codes[index], next ? { ...state, next } : state];
				})
			);
			return { first: codes[0], states };
		}
	};
}

/**
 * A decision module: a question and a decision on its answer. The decision has one rule for each answer but the
 * last, which takes the default route, and every route is left loose for the person to join. The decision is given
 * a title, as every module state is, and the person can write over it.
 */
function decideOn(questionName: string, schema: InputState['schema'], rulesFor: (answer: string) => WorkingState): ModuleDefinition {
	return {
		build: (code) => {
			const ask = code('ask');
			const decide = code('decide');
			const question = input(ask, questionName, schema);
			return { first: ask, states: { [ask]: { ...question, next: decide }, [decide]: { ...rulesFor(placeholderAnswerVariable(ask)), name: 'Question decision' } } };
		}
	};
}

// The words of the start page, laid out like a GOV.UK start page so the person can see what goes where.
const startPageMessage = [
	'Use this service to [what the service lets someone do].',
	'Before you start',
	'You will need:',
	'- [the first thing they need]',
	'- [the second thing they need]',
	'It takes around [number] minutes to complete.'
].join('\n\n');

// The payment link sits in the message, because there is no payment service to call. The address is on a reserved
// example domain, so it can never reach a real page before the person replaces it.
const paymentMessage = 'Pay for [what the person is paying for]: [Pay now](https://www.example.gov.uk/pay)';

const phoneCallMessage = 'Call [team name] on [phone number]. Lines are open [days and times].';

const letterMessage = 'Post your form to:\n\n[Team name]\n[Address line 1]\n[Town or city]\n[Postcode]';

// The formats offered by the Formatted question, for contact details and dates, and by the ID questions, for
// reference numbers.
const contactFormats: AnswerFormatKey[] = ['email', 'phone_number', 'postcode', 'date'];
const idNumberFormats: AnswerFormatKey[] = [
	'national_insurance_number',
	'utr',
	'passport',
	'driving_licence',
	'vat_number',
	'company_number',
	'vehicle_registration'
];

// How long the deadline, the phone call and the letter wait. They are placeholders that the technical review sets.
const deadlineWait = 'P28D';
const phoneCallWait = 'P1D';
const letterWait = 'P7D';

export const moduleDefinitions: Record<ModuleKey, ModuleDefinition> = {
	start_page: single(() => output('Start information', startPageMessage)),
	message: single(() => output('Message')),

	simple_question: single((code) => input(code, 'Question')),
	formatted_question: { ...single((code) => input(code, 'Formatted question')), answerFormats: contactFormats },
	boolean_question: single((code) => input(code, 'Yes or no question', { kind: 'boolean' })),
	select_one: single((code) => input(code, 'Select one question', { kind: 'select_one', options: placeholderOptions(2) })),
	select_many: single((code) => input(code, 'Select many question', { kind: 'select_many', options: placeholderOptions(3) })),
	data_question: { ...single((code) => input(code, 'ID number question')), answerFormats: idNumberFormats },

	// The add another loop: the answer is added to a list, the person is asked whether there is another, and a yes
	// goes back to the question. It is written the way the form files write it, as in the trainer example.
	many_answers: {
		build: (code) => {
			const [ask, keep, more, again] = ['ask', 'keep', 'more', 'again'].map(code);
			const list = placeholderAnswerVariable(ask);
			return {
				first: ask,
				states: {
					[ask]: { state_type: 'input', name: 'Question', ...placeholderInput(ask), assign: `repeat.${list}.current`, next: keep },
					[keep]: {
						state_type: 'assign',
						name: 'Append answer',
						set: { [list]: { op: 'append', path: list, value_path: `repeat.${list}.current` } },
						next: more
					},
					[more]: {
						state_type: 'input',
						name: 'Add another answer',
						prompt: 'Do you want to add another answer?',
						schema: { kind: 'boolean' },
						assign: `repeat.${list}.more`,
						next: again
					},
					[again]: { state_type: 'choice', name: 'Repeat question', rules: [{ when: { op: 'is_true', path: `repeat.${list}.more` }, next: ask }] }
				}
			};
		}
	},

	choice_decision: {
		...decideOn('Select one question', { kind: 'select_one', options: placeholderOptions(2) }, (answer) => ({
			state_type: 'choice',
			rules: [{ when: { op: 'eq', path: answer, value: 'option_1' } }]
		})),
		addsRoutesForOptions: true
	},
	boolean_decision: decideOn('Yes or no question', { kind: 'boolean' }, (answer) => ({
		state_type: 'choice',
		rules: [{ when: { op: 'is_true', path: answer } }]
	})),
	// An ID the person may not have, so the question can be left blank and the decision routes on whether it was.
	data_decision: {
		...decideOn('ID number question', { kind: 'string', allow_skip: true }, (answer) => ({
			state_type: 'choice',
			rules: [{ when: { op: 'not_empty', path: answer } }]
		})),
		answerFormats: idNumberFormats
	},

	// The flow is as the executor team gave it, and may change once the deadline is clarified with them.
	deadline: chain([
		['tell', () => output('Deadline', 'You must finish this form by [date].')],
		['pause', () => ({ state_type: 'wait', name: 'Wait until deadline', duration: deadlineWait })],
		['ask', (code) => input(code, 'Deadline question')],
		['after', () => output('After the deadline')]
	]),
	wait: single(() => ({ state_type: 'wait', name: 'Wait', duration: placeholderWaitDuration })),

	user_details: {
		build: (code) => {
			const [tell, ask, fetch, show, failed] = ['tell', 'ask', 'fetch', 'show', 'failed'].map(code);
			return {
				first: tell,
				states: {
					[tell]: { ...output('Before getting your details'), next: ask },
					[ask]: { ...input(ask, 'Details question'), next: fetch },
					[fetch]: {
						state_type: 'api_call',
						name: 'Get user details',
						...unconnectedApiCallDetails,
						catch: [{ on: 'any', next: failed }],
						next: show
					},
					[show]: output('Your details'),
					[failed]: placeholderFailedEnd
				}
			};
		}
	},

	// The submit and check loop, as in the trainer example: the answers are sent, the person is told, and the
	// submission is checked after a wait until it has been processed. Either call failing ends the journey.
	submit: {
		build: (code) => {
			const [send, tell, pause, check, processed, done, failed] = ['send', 'tell', 'pause', 'check', 'processed', 'done', 'failed'].map(code);
			return {
				first: send,
				states: {
					[send]: {
						state_type: 'api_call',
						name: 'Submit form',
						...unconnectedApiCallDetails,
						method: 'POST',
						capture: { submission_id: 'body.submission_id' },
						catch: [{ on: 'any', next: failed }],
						next: tell
					},
					[tell]: { ...output('What happens next', 'Your form has been submitted.'), next: pause },
					[pause]: { state_type: 'wait', name: 'Wait for the form to be processed', duration: 'PT30M', next: check },
					[check]: {
						state_type: 'api_call',
						name: 'Check submission',
						...unconnectedApiCallDetails,
						capture: { submission_status: 'body.status' },
						catch: [{ on: 'any', next: failed }],
						next: processed
					},
					[processed]: {
						state_type: 'choice',
						name: 'Submission processed',
						rules: [{ when: { op: 'eq', path: 'submission_status', value: 'processed' }, next: done }],
						default: pause
					},
					[done]: { state_type: 'end', name: 'Process complete', status: 'success' },
					[failed]: placeholderFailedEnd
				}
			};
		}
	},

	payment: single(() => output('Payment', paymentMessage)),

	// The person is sent away to do this offline, with no way to carry on digitally.
	information: {
		build: (code) => {
			const [tell, leave] = ['tell', 'leave'].map(code);
			return { first: tell, states: { [tell]: { ...output('Offline information'), next: leave }, [leave]: { state_type: 'end', name: 'Continue offline', status: 'offramp' } } };
		}
	},
	phone_call: chain([
		['tell', () => output('Phone call details', phoneCallMessage)],
		['pause', () => ({ state_type: 'wait', name: 'Wait for phone call', duration: phoneCallWait })],
		['ask', (code) => input(code, 'Have you rung us', { kind: 'boolean' }, 'Have you rung us?')],
		['after', () => output('After the phone call')]
	]),
	letter: chain([
		['tell', () => output('Letter details', letterMessage)],
		['pause', () => ({ state_type: 'wait', name: 'Wait for letter', duration: letterWait })],
		['ask', (code) => input(code, 'Have you posted it', { kind: 'boolean' }, 'Have you posted it?')],
		['after', () => output('After the letter')]
	])
};
