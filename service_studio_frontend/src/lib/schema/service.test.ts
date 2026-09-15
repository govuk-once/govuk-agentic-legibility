import { describe, expect, it } from 'vitest';
import validExample from '$lib/examples/change-driving-licence-address.json';
import { parseService } from './validate';

/**
 * Returns a deep, mutable copy of the valid example so each test can break one thing without affecting
 * the others. Typed loosely on purpose, since every test here deliberately writes an invalid value.
 */
function brokenCopy(): any {
	return structuredClone(validExample);
}

describe('canonical service schema', () => {
	it('accepts a valid RFC-shaped service definition', () => {
		const result = parseService(validExample);
		expect(result.ok).toBe(true);
	});

	it('rejects a startStepId that is not one of the steps', () => {
		const broken = brokenCopy();
		broken.startStepId = '00000000-0000-4000-8000-000000000000';
		const result = parseService(broken);

		expect(result.ok).toBe(false);
		if (!result.ok) {
			expect(result.issues.some((issue) => issue.path === 'startStepId')).toBe(true);
		}
	});

	it('rejects a transition that targets a missing step', () => {
		const broken = brokenCopy();
		broken.steps[1].transitions[0].targetStepId = '00000000-0000-4000-8000-000000000000';
		const result = parseService(broken);

		expect(result.ok).toBe(false);
		if (!result.ok) {
			expect(result.issues.some((issue) => issue.path.includes('transitions'))).toBe(true);
		}
	});

	it('rejects duplicate step ids', () => {
		const broken = brokenCopy();
		broken.steps[1].id = broken.steps[0].id;
		const result = parseService(broken);

		expect(result.ok).toBe(false);
		if (!result.ok) {
			expect(result.issues.some((issue) => issue.message.toLowerCase().includes('duplicate'))).toBe(true);
		}
	});

	it('rejects an unknown step type kind', () => {
		const broken = brokenCopy();
		broken.steps[0].type.kind = 'sms';
		const result = parseService(broken);

		expect(result.ok).toBe(false);
	});

	it('rejects a non-ISO date in a step window', () => {
		const broken = brokenCopy();
		broken.steps[0].window = { start: '1 April 2026', end: '2026-05-01' };
		const result = parseService(broken);

		expect(result.ok).toBe(false);
	});
});
