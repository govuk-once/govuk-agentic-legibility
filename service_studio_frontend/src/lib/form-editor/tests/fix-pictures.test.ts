import { describe, expect, it } from 'vitest';
import { wordsFor, type JourneyProblemKind } from '$lib/schema/workflow/journey-problems';
import { fixPictures } from '$lib/form-editor/fix-pictures';

// Every sort of problem but the schema's, which has its own words and neither a picture nor a how to fix line.
const kinds: Exclude<JourneyProblemKind, 'schema'>[] = [
	'no_start',
	'no_next',
	'way_out_leads_nowhere',
	'not_joined',
	'placeholder_question',
	'placeholder_message',
	'rule_to_confirm'
];

describe('fixPictures', () => {
	it('gives every sort of problem either a picture or a how to fix line, and never both', () => {
		for (const kind of kinds) {
			const hasPicture = fixPictures[kind] !== undefined;
			const hasLine = wordsFor(kind).howToFix !== undefined;
			expect(hasPicture !== hasLine, kind).toBe(true);
		}
	});

	it('describes every picture in words for a screen reader', () => {
		for (const picture of Object.values(fixPictures)) expect(picture.description).toMatch(/^Before: .+ After: .+/);
	});
});
