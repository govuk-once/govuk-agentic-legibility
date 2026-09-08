export type AnswerType = 'question-group' | 'single-question' | 'file-upload' | 'declaration';

// The shape every step in a journey shares. A step number is deliberately not stored here, it is always
// derived from the step's position in the list, so it can never go out of step after an add, remove or
// reorder.
export type JourneyStep = {
	id: string;
	title: string;
	description: string;
	tagLabel: string;
	tagColour: string;
	answerType: AnswerType;
	branchesTo: string | null;
};
