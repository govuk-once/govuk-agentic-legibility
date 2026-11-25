import { describe, expect, it } from 'vitest';
import { serviceSchema } from './service';
import { defaultStepType, humanKind, kindColour } from './step-kind';

const KINDS = ['info', 'endpoint', 'phone', 'person', 'letter'] as const;

describe('defaultStepType', () => {
	it('produces a valid type object for every step kind', () => {
		for (const kind of KINDS) {
			const service = {
				id: '00000000-0000-4000-8000-000000000000',
				version: 1,
				state: 'draft',
				name: 'x',
				owner: 'gds',
				contact: 'x@y.gov.uk',
				description: '',
				descriptionPublic: '',
				startStepId: '00000000-0000-4000-8000-000000000001',
				steps: [
					{
						id: '00000000-0000-4000-8000-000000000001',
						type: defaultStepType(kind),
						name: 'x',
						description: '',
						fields: [],
						transitions: []
					}
				]
			};

			const result = serviceSchema.safeParse(service);
			expect(result.success, `${kind}: ${JSON.stringify(result.error?.issues)}`).toBe(true);
			expect(defaultStepType(kind).kind).toBe(kind);
		}
	});
});

describe('step kind labels', () => {
	it('maps kinds to human labels and GOV.UK tag colours', () => {
		expect(humanKind('endpoint')).toBe('API endpoint');
		expect(humanKind('person')).toBe('In person');
		expect(kindColour('info')).toBe('grey');
		expect(kindColour('phone')).toBe('purple');
	});
});
