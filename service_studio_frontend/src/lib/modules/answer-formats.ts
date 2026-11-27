import { answerTypeKey } from '$lib/schema/workflow/answer-types';
import { withNote } from '$lib/schema/workflow/edit-state';
import type { AnswerDefinition } from '$lib/schema/workflow/input-state';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import { isModuleKey } from '$lib/modules/add-module';
import { moduleDefinitions } from '$lib/modules/module-states';

/*
	The formats a typed answer can be checked against, such as an email address or a National Insurance number.
	Choosing a format fills in the pattern the answer must match, the message shown when it does not, and how the
	answer is tidied before it is checked. The person never writes a pattern.

	1. The module an input came from says which formats it offers, so the Formatted question offers contact details
	   and dates, and the ID questions offer reference numbers. An input that is not from such a module offers none.
	2. Each format is named by its answer type, the note in the metadata that says what sort of typed answer a
	   question takes, such as email. Choosing a format writes that answer type, so the card can show the choice
	   again, and one note says both what the answer is and how it is checked.
	3. The patterns for email, phone, postcode, date, National Insurance number and Unique Taxpayer Reference are
	   copied from the example services, and each names the file it came from. The others are written here and
	   need to be replaced with the patterns the team uses.
*/

// The answer types that have a format to check against. Each is also in the list of answer types for a typed answer.
export type AnswerFormatKey =
	| 'email'
	| 'phone_number'
	| 'postcode'
	| 'date'
	| 'national_insurance_number'
	| 'utr'
	| 'passport'
	| 'driving_licence'
	| 'vat_number'
	| 'company_number'
	| 'vehicle_registration';

export interface AnswerFormat {
	label: string;
	pattern: string;
	invalidMessage: string;
	normalise?: 'upper_trim' | 'lower_trim';
}

export const answerFormats: Record<AnswerFormatKey, AnswerFormat> = {
	// From services/change_of_address/driver_details.json, prompt_manual_email.
	email: {
		label: 'Email address',
		pattern: '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$',
		invalidMessage: 'Please enter a valid email address (e.g., name@example.com).',
		normalise: 'lower_trim'
	},
	// From services/maternity_allowance/about_you.json, prompt_manual_phone.
	phone_number: {
		label: 'UK phone number',
		pattern: '^(?:0|\\+?44)\\d{9,10}$',
		invalidMessage: 'Please enter a valid UK telephone number.'
	},
	// From services/maternity_allowance/about_you.json, prompt_manual_postcode. The pattern only accepts capital
	// letters, so the answer is put into capitals first.
	postcode: {
		label: 'UK postcode',
		pattern: '^[A-Z]{1,2}[0-9][A-Z0-9]?\\s?[0-9][A-Z]{2}$',
		invalidMessage: 'Please enter a valid UK postcode.',
		normalise: 'upper_trim'
	},
	// From services/maternity_allowance/about_baby.json, prompt_actual_birth_date.
	date: {
		label: 'Date (DD/MM/YYYY)',
		pattern: '^(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[012])/(19|20)\\d{2}$',
		invalidMessage: 'Please enter a valid date in DD/MM/YYYY format.'
	},
	// From services/maternity_allowance/about_you.json, prompt_nino.
	national_insurance_number: {
		label: 'National Insurance number',
		pattern: '^[A-CEGHJ-PR-TW-Z]{1}[A-CEGHJ-NPR-TW-Z]{1}[0-9]{6}[A-D]{1}$',
		invalidMessage: 'Please enter a valid UK National Insurance number.',
		normalise: 'upper_trim'
	},
	// From services/maternity_allowance/about_work.json, prompt_se_utr.
	utr: {
		label: 'Unique Taxpayer Reference',
		pattern: '^[0-9]{10}$',
		invalidMessage: 'Unique Taxpayer Reference must be exactly 10 digits.'
	},
	// Written here and not taken from an example. To be replaced with the pattern the team uses.
	passport: {
		label: 'UK passport number',
		pattern: '^[0-9]{9}$',
		invalidMessage: 'Passport number must be 9 digits.'
	},
	// Written here and not taken from an example. To be replaced with the pattern the team uses.
	driving_licence: {
		label: 'UK driving licence number',
		pattern: '^[A-Z9]{5}[0-9]{6}[A-Z9]{2}[0-9][A-Z]{2}$',
		invalidMessage: 'Driving licence number must be 16 characters, as shown on the licence.',
		normalise: 'upper_trim'
	},
	// Written here and not taken from an example. To be replaced with the pattern the team uses.
	vat_number: {
		label: 'VAT registration number',
		pattern: '^(GB)?[0-9]{9}([0-9]{3})?$',
		invalidMessage: 'VAT registration number must be 9 or 12 digits, and may start with GB.',
		normalise: 'upper_trim'
	},
	// Written here and not taken from an example. To be replaced with the pattern the team uses.
	company_number: {
		label: 'Company registration number',
		pattern: '^([0-9]{8}|[A-Z]{2}[0-9]{6})$',
		invalidMessage: 'Company registration number must be 8 characters.',
		normalise: 'upper_trim'
	},
	// Written here and not taken from an example. It only accepts the current style of number plate, such as AB12 CDE,
	// and is to be replaced with the pattern the team uses.
	vehicle_registration: {
		label: 'Vehicle registration number',
		pattern: '^[A-Z]{2}[0-9]{2}\\s?[A-Z]{3}$',
		invalidMessage: 'Please enter a valid vehicle registration number.',
		normalise: 'upper_trim'
	}
};

/**
 * Lists the formats an input offers, which are the ones the module it came from names. An input that did not come
 * from a module, or from one that names no formats, offers none.
 */
export function formatsFor(state: WorkingState): AnswerFormatKey[] {
	const group = state.metadata?.group;
	return typeof group === 'string' && isModuleKey(group) ? (moduleDefinitions[group].answerFormats ?? []) : [];
}

/**
 * Tells whether a value names one of the formats, such as one read back from metadata or from a list of choices.
 */
export function isAnswerFormatKey(value: unknown): value is AnswerFormatKey {
	return typeof value === 'string' && Object.hasOwn(answerFormats, value);
}

/**
 * Reads the format of an input's answer from its answer type, or nothing when its answer type has no format, such as
 * name or address, or it has none.
 */
export function answerFormatOf(state: WorkingState): AnswerFormatKey | undefined {
	const answerType = state.metadata?.[answerTypeKey];
	return isAnswerFormatKey(answerType) ? answerType : undefined;
}

// A typed answer, the only kind of answer a format can be checked on.
type TypedAnswer = Extract<AnswerDefinition, { kind: 'string' }>;

/**
 * Gives a typed answer the pattern, message and tidying of a format, or takes all three away when there is no format.
 * Used by the card and by a drafted form, so both check an answer in the same way.
 */
export function withFormatCheck(schema: TypedAnswer, key: AnswerFormatKey | undefined): TypedAnswer {
	const checked = { ...schema };
	const format = key === undefined ? undefined : answerFormats[key];
	if (format) {
		checked.pattern = format.pattern;
		checked.invalid_message = format.invalidMessage;
		if (format.normalise) checked.normalise = format.normalise;
		else delete checked.normalise;
	} else {
		delete checked.pattern;
		delete checked.invalid_message;
		delete checked.normalise;
	}
	return checked;
}

/**
 * Gives a typed input the pattern, message and tidying of a format, and writes the format as its answer type.
 * Choosing no format takes all of them away, and takes away an answer type that was a format. An answer type with
 * no format, such as name, is kept. Any other state is returned as it is.
 */
export function withAnswerFormat(state: WorkingState, key: AnswerFormatKey | undefined): WorkingState {
	if (state.state_type !== 'input' || state.schema.kind !== 'string') return state;

	const formatted = { ...state, schema: withFormatCheck(state.schema, key) };
	if (key !== undefined) return withNote(formatted, answerTypeKey, key);
	return answerFormatOf(state) === undefined ? formatted : withNote(formatted, answerTypeKey, '');
}
