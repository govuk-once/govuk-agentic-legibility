import { describe, expect, it } from 'vitest';
import {
	durationOrRefSchema,
	durationSchema,
	dynamicRefSchema,
	metadataSchema,
	processRefSchema,
	stateRefSchema,
	variablePathSchema
} from './primitives';

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

	it('rejects values that are not text', () => {
		expect(metadataSchema.safeParse({ attempts: 3 }).success).toBe(false);
		expect(metadataSchema.safeParse({ nested: { a: 'b' } }).success).toBe(false);
	});
});
