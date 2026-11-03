import { describe, expect, it } from 'vitest';
import { exampleProcessFiles } from '../schema/workflow/example-states';
import { tidyCode } from './tidy-code';

describe('tidyCode', () => {
	it.each([
		['confirm_intent', 'Confirm intent'],
		['end_rejected', 'End rejected'],
		['poll-job', 'Poll job'],
		['uploadPhoto', 'Upload photo'],
		['upload_photo_2', 'Upload photo 2'],
		['__start__', 'Start'],
		['Confirm intent', 'Confirm intent'],
		['wait', 'Wait']
	])('turns %s into %s', (code, label) => {
		expect(tidyCode(code)).toBe(label);
	});

	it('keeps an acronym in capitals', () => {
		expect(tidyCode('check_DVLA_record')).toBe('Check DVLA record');
		expect(tidyCode('uploadMATB1')).toBe('Upload MATB1');
	});

	it('gives an empty label for an empty code or one made only of separators', () => {
		expect(tidyCode('')).toBe('');
		expect(tidyCode('___')).toBe('');
	});

	it('gives every state in the real examples a readable label', () => {
		const codes = exampleProcessFiles().flatMap((file) => Object.keys((file as { states: object }).states));
		expect(codes.length).toBeGreaterThan(200);

		for (const code of codes) {
			const label = tidyCode(code);
			expect(label, code).not.toBe('');
			expect(label, code).not.toMatch(/[_.-]/);
			expect(label, code).toMatch(/^[A-Z0-9]/);
		}
	});
});
