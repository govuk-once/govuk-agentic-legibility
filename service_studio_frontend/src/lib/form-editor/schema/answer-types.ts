import type { AnswerDefinition } from '$lib/schema/workflow/input-state';

/*
	The answer type of a question in a form. The kind of answer in the schema says how an answer is given: typed,
	yes or no, chosen from options or uploaded. The answer type is a finer note kept with the question, which says
	what a typed answer is, such as an email address or a date, so the form can show the right kind of box. The
	words are the ones the existing forms use.
*/

// The key in the notes of a question that holds its answer type.
export const answerTypeKey = 'answer_type';

// The answer types that go with each kind of answer. The first of each list is the one given to a question whose
// answer type is not known. The record is keyed by every kind of answer, so adding a kind to the schema without
// saying which answer types it takes fails to compile.
export const answerTypesByKind: Record<AnswerDefinition['kind'], readonly string[]> = {
	string: ['text', 'name', 'number', 'email', 'address', 'date', 'phone_number', 'national_insurance_number', 'organisation_name'],
	boolean: ['selection'],
	select_one: ['selection'],
	select_many: ['selection'],
	file_ref: ['file']
};
