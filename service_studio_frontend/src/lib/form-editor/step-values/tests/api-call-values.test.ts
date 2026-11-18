import { describe, expect, it } from 'vitest';
import type { ApiCallState } from '$lib/schema/workflow/api-call-state';
import { placeholderBodyValue } from '$lib/schema/workflow/placeholders';
import { apiCallFields, apiCallValuesOf, apiCallWithValues, savedAnswerExample } from '../api-call-values';

const call: ApiCallState = {
	state_type: 'api_call',
	name: 'Send form',
	method: 'POST',
	service: 'govuk_forms',
	url: '/send',
	body: { name: { $: 'answers.name' } },
	assign: 'reply',
	capture: { reply_id: 'body.id' },
	next: 'done'
};

describe('apiCallValuesOf', () => {
	it('writes the body as JSON over several lines and an unset save name as empty', () => {
		const { assign: _assign, ...unsaved } = call;
		expect(apiCallValuesOf(unsaved)).toMatchObject({ assign: '', body: JSON.stringify(call.body, null, 2) });
	});
});

describe('apiCallWithValues', () => {
	const typed = apiCallValuesOf(call);

	it('reads the typed values into the call and keeps what is not typed', () => {
		const result = apiCallWithValues(call, { ...typed, method: 'PUT', url: ' /send/v2 ', body: '{"name": "fixed"}' });
		expect(result).toEqual({ ok: true, state: { ...call, method: 'PUT', url: '/send/v2', body: { name: 'fixed' } } });
	});

	it('leaves out the body and save name when they are emptied', () => {
		const result = apiCallWithValues(call, { ...typed, assign: '', body: '' });
		expect(result.ok && result.state).not.toHaveProperty('body');
		expect(result.ok && result.state).not.toHaveProperty('assign');
	});

	it('names each field that must be put right', () => {
		const result = apiCallWithValues(call, { ...typed, url: '', service: ' ', assign: 'not a name', body: '{' });
		expect(result.ok ? [] : result.problems.map((problem) => problem.field)).toEqual([
			apiCallFields.url,
			apiCallFields.service,
			apiCallFields.assign,
			apiCallFields.body
		]);
	});

	it('refuses a body that still has a field to fill in', () => {
		const result = apiCallWithValues(call, { ...typed, body: JSON.stringify({ declaration: placeholderBodyValue }) });
		expect(result).toEqual({ ok: false, problems: [{ field: apiCallFields.body, message: 'Give declaration a value in the body' }] });
	});
});

describe('savedAnswerExample', () => {
	it('writes the first field that sends a saved answer, passing over fixed values and placeholders', () => {
		expect(savedAnswerExample({ declaration: placeholderBodyValue, kind: 'form', name: { $: 'answers.name' } })).toEqual({
			field: '{"name":{"$":"answers.name"}}',
			value: '{"$":"answers.name"}'
		});
	});

	it('gives nothing for a body with no saved answers', () => {
		expect(savedAnswerExample({ kind: 'form' })).toBeUndefined();
		expect(savedAnswerExample(undefined)).toBeUndefined();
	});
});
