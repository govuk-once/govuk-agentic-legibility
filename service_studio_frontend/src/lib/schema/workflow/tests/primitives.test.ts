import { describe, expect, it } from 'vitest';
import {
	durationOrRefSchema,
	durationSchema,
	dynamicRefSchema,
	metadataSchema,
	textNoteKeys,
	processRefSchema,
	stateRefSchema,
	variablePathSchema,
	versionSchema
} from '../primitives';

describe('variablePathSchema', () => {
	// Paths copied from the change of address and maternity allowance examples.
	it.each(['upload_attempts', 'photocard_res.expired', 'body.photo.icaoCompliant', 'input.due_date', '__now__'])(
		'accepts %s',
		(path) => {
			expect(variablePathSchema.safeParse(path).success).toBe(true);
		}
	);

	it.each(['', '.leading', 'trailing.', 'double..dot', 'has space', '1starts_with_digit', 'a-b'])(
		'rejects "%s"',
		(path) => {
			expect(variablePathSchema.safeParse(path).success).toBe(false);
		}
	);
});

describe('durationSchema', () => {
	it.each(['PT2S', 'PT24H', 'P14D', 'P90D'])('accepts %s', (duration) => {
		expect(durationSchema.safeParse(duration).success).toBe(true);
	});

	it.each(['two days', '14 days', '14D', '', 5])('rejects %s', (duration) => {
		expect(durationSchema.safeParse(duration).success).toBe(false);
	});
});

describe('dynamicRefSchema', () => {
	it('accepts a reference to a variable', () => {
		expect(dynamicRefSchema.safeParse({ $: 'driver.email' }).success).toBe(true);
	});

	it('rejects a reference with an invalid path', () => {
		expect(dynamicRefSchema.safeParse({ $: 'driver email' }).success).toBe(false);
	});

	it('rejects a reference with extra keys', () => {
		expect(dynamicRefSchema.safeParse({ $: 'driver.email', fallback: 'none' }).success).toBe(false);
	});

	it('rejects a reference with no path', () => {
		expect(dynamicRefSchema.safeParse({}).success).toBe(false);
	});
});

describe('durationOrRefSchema', () => {
	it('accepts a written duration', () => {
		expect(durationOrRefSchema.safeParse('PT10S').success).toBe(true);
	});

	it('accepts a reference to a variable that holds a duration', () => {
		expect(durationOrRefSchema.safeParse({ $: 'poll_interval' }).success).toBe(true);
	});

	it('rejects anything else', () => {
		expect(durationOrRefSchema.safeParse('soon').success).toBe(false);
		expect(durationOrRefSchema.safeParse(10).success).toBe(false);
	});
});

describe('versionSchema', () => {
	it.each(['0.1.0', '1.0.0', '12.34.56', '1.0.0-beta.1'])('accepts %s', (version) => {
		expect(versionSchema.safeParse(version).success).toBe(true);
	});

	it.each(['1', '1.0', 'v1.0.0', '1.0.0.0', '01.0.0', '', 1])('rejects %s', (version) => {
		expect(versionSchema.safeParse(version).success).toBe(false);
	});
});

describe('stateRefSchema', () => {
	it('accepts the name of a state', () => {
		expect(stateRefSchema.safeParse('confirm_intent').success).toBe(true);
	});

	it('rejects an empty name and a value that is not text', () => {
		expect(stateRefSchema.safeParse('').success).toBe(false);
		expect(stateRefSchema.safeParse(null).success).toBe(false);
	});
});

describe('processRefSchema', () => {
	it('accepts the name of a process', () => {
		expect(processRefSchema.safeParse('driver_details').success).toBe(true);
	});

	it('rejects an empty name and a value that is not text', () => {
		expect(processRefSchema.safeParse('').success).toBe(false);
		expect(processRefSchema.safeParse(3).success).toBe(false);
	});
});

describe('metadataSchema', () => {
	it('accepts an empty map and text entries', () => {
		expect(metadataSchema.safeParse({}).success).toBe(true);
		expect(metadataSchema.safeParse({ description: 'Checks the licence number.' }).success).toBe(true);
	});

	it('accepts a value of any kind that JSON can hold, in a note that Service Studio does not read', () => {
		const notes = {
			position: 3,
			optional: true,
			repeatable: false,
			language: null,
			available_languages: ['en', 'cy'],
			answer_settings: { only_one_option: 'true', selection_options: [{ name: 'Yes', value: 'Yes', is_other: false }] }
		};
		expect(metadataSchema.safeParse(notes).success).toBe(true);
	});

	it('keeps every note exactly as it was written, including nested ones', () => {
		const notes = { position: 3, answer_settings: { selection_options: [{ name: 'Yes' }] }, hint_text: null };
		expect(metadataSchema.parse(notes)).toEqual(notes);
	});

	it.each(textNoteKeys)('accepts the note %s as text, as null, or not at all', (key) => {
		expect(metadataSchema.safeParse({ [key]: 'Some words.' }).success).toBe(true);
		expect(metadataSchema.safeParse({ [key]: null }).success).toBe(true);
		expect(metadataSchema.safeParse({}).success).toBe(true);
	});

	it.each(textNoteKeys)('refuses the note %s when it is not text, because it is shown as words', (key) => {
		for (const value of [3, true, ['a'], { a: 'b' }]) {
			const result = metadataSchema.safeParse({ [key]: value });
			expect(result.success, `${key}: ${JSON.stringify(value)}`).toBe(false);
			expect(result.error?.issues[0].path).toEqual([key]);
		}
	});

	it('refuses a value that JSON cannot hold', () => {
		expect(metadataSchema.safeParse({ when: new Date() }).success).toBe(false);
		expect(metadataSchema.safeParse({ nothing: undefined }).success).toBe(false);
	});
});
