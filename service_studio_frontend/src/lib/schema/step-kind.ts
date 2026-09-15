import type { ServiceStep, ServiceStepKind } from './service';

// How each step kind is described and coloured in the editor list and the graph. The colour names are
// GOV.UK tag modifiers, so a kind reads as its own tag without any new colour system.
const KIND_LABELS: Record<ServiceStepKind, string> = {
	endpoint: 'API endpoint',
	phone: 'Phone',
	person: 'In person',
	letter: 'Letter',
	info: 'Information'
};

const KIND_COLOURS: Record<ServiceStepKind, string> = {
	endpoint: 'blue',
	phone: 'purple',
	person: 'green',
	letter: 'yellow',
	info: 'grey'
};

/**
 * Returns the human readable label for a step kind, for example "API endpoint" for "endpoint".
 */
export function humanKind(kind: ServiceStepKind): string {
	return KIND_LABELS[kind];
}

/**
 * Returns the GOV.UK tag colour name for a step kind, for use in a govuk-tag--{colour} class.
 */
export function kindColour(kind: ServiceStepKind): string {
	return KIND_COLOURS[kind];
}

/**
 * Returns the smallest valid type object for a step kind, used when the editor changes a step's kind
 * and the previous kind's delivery details (a call contract, opening times, an address) no longer
 * apply. Placeholder strings are used where the schema needs a value, for example the endpoint url,
 * so the result still passes validation and the real detail can be filled in later.
 */
export function defaultStepType(kind: ServiceStepKind): ServiceStep['type'] {
	switch (kind) {
		case 'endpoint':
			return {
				kind: 'endpoint',
				method: 'GET',
				url: 'https://example.gov.uk',
				parameters: [],
				headers: [],
				responses: []
			};
		case 'phone':
			return { kind: 'phone', number: '', openingTimes: { periods: [] } };
		case 'person':
			return {
				kind: 'person',
				location: { line1: '', town: '', postcode: '' },
				openingTimes: { periods: [] }
			};
		case 'letter':
			return { kind: 'letter', address: { line1: '', town: '', postcode: '' } };
		case 'info':
		default:
			return { kind: 'info', body: '' };
	}
}
