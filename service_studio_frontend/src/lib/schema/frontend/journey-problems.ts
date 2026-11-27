import { placeholderMessage, placeholderQuestion } from	'$lib/schema/frontend/placeholders';

/*
	The words for each sort of problem a journey that is being edited can have. They are kept together here so they
	can be read and changed in one place, while validate.ts only finds the problems.

	1. The message follows the name of the state the problem is about, such as "has nothing after it", for the list the
	   check before proceeding gives.
	2. The title names the problem on its own in a list of problems, and the fix says what to do about it. A problem
	   that is about wording and not about how steps connect also has a short how to fix line, for the column of a
	   list that otherwise shows how to connect the steps.
	3. A message or title that counts something, such as the ways out of a decision that lead nowhere, is given the
	   count. Words that count nothing leave it unused.
*/

export type JourneyProblemKind =
	'no_start' | 'no_next' | 'way_out_leads_nowhere' | 'not_joined' | 'schema' | 'placeholder_question' | 'placeholder_message' | 'rule_to_confirm';

// Whether a problem stops a journey being passed on, which an error does, or is only worth finishing, which a warning
// is.
export type ProblemSeverity = 'error' | 'warning';

type ProblemWords = { message: (count: number) => string; title: (count: number) => string; fix: string; howToFix?: string };

// The schema writes its own words for what is wrong, so a problem it finds only has a title here, and the schema's
// words are its fix.
export const schemaProblemTitle = 'Does not match the schema';

// Keyed by every sort of problem but the schema's, so adding a sort without its words fails to compile.
const journeyProblemWords: Record<Exclude<JourneyProblemKind, 'schema'>, ProblemWords> = {
	no_start: {
		message: () => 'The journey has no start. Draw a line from the start dot to the first step.',
		title: () => 'No start',
		fix: 'Draw a line from the start dot to the first step.'
	},
	no_next: { message: () => 'has nothing after it', title: () => 'No next step', fix: 'Add a next step, or make this the last step.' },
	way_out_leads_nowhere: {
		message: (count) => (count === 1 ? 'has a way out that leads nowhere' : `has ${count} ways out that lead nowhere`),
		title: (count) => (count === 1 ? 'A way out leads nowhere' : `${count} ways out lead nowhere`),
		fix: 'Choose which step comes next for every answer.'
	},
	not_joined: { message: () => 'is not joined to the journey', title: () => 'Not joined to the journey', fix: 'Connect a step to it, or delete it.' },
	placeholder_question: {
		message: () => `still has the placeholder question "${placeholderQuestion}"`,
		title: () => 'Placeholder question',
		fix: `The question still says "${placeholderQuestion}". Replace it with the real question.`,
		howToFix: 'Update placeholder wording'
	},
	placeholder_message: {
		message: () => `still has the placeholder message "${placeholderMessage}"`,
		title: () => 'Placeholder message',
		fix: `The message still says "${placeholderMessage}". Replace it with the real wording.`,
		howToFix: 'Update placeholder wording'
	},
	rule_to_confirm: {
		message: (count) => (count === 1 ? 'has a rule still to be confirmed' : `has ${count} rules still to be confirmed`),
		title: (count) => (count === 1 ? 'Rule to be confirmed' : `${count} rules to be confirmed`),
		fix: 'Choose what the decision checks before each route.',
		howToFix: 'Update the placeholder rule'
	}
};

/**
 * Gives the sort of a problem with its message, title, fix and how to fix line, for the given count of what it counts.
 */
export function wordsFor(kind: Exclude<JourneyProblemKind, 'schema'>, count = 1) {
	const words = journeyProblemWords[kind];
	return { kind, message: words.message(count), title: words.title(count), fix: words.fix, howToFix: words.howToFix };
}
