import { describe, expect, it } from 'vitest';
import { formExamples } from '$lib/examples/forms';
import { answerTypeKey, answerTypesByKind } from '../schema/answer-types';

describe('answerTypesByKind', () => {
	it('gives every kind of answer at least one answer type, with the most general first', () => {
		for (const [kind, types] of Object.entries(answerTypesByKind)) expect(types.length, kind).toBeGreaterThan(0);
		expect(answerTypesByKind.string[0]).toBe('text');
	});

	it('lists the answer type of every question in the form examples under the kind of answer it has', () => {
		// Every question of every form, with the kind of answer and the answer type it was loaded with.
		const questions = formExamples.flatMap((example) =>
			Object.values(example.workflow?.processes ?? {}).flatMap((process) =>
				Object.entries(process.states).flatMap(([code, state]) =>
					state.state_type === 'input' ? [{ where: `${example.slug}: ${code}`, kind: state.schema.kind, type: state.metadata?.[answerTypeKey] }] : []
				)
			)
		);
		const withType = questions.filter((question) => typeof question.type === 'string');

		expect(withType.length).toBeGreaterThan(200);
		for (const question of withType) expect(answerTypesByKind[question.kind], question.where).toContain(question.type);
	});
});
