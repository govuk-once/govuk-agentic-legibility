import type { FlexEndpoint } from '$lib/form-editor/flex-connections';

/*
	A few made up endpoints for the "Find the endpoint" page to show until the real Flex list is ready. They match the
	demo form that submits its answers, so the page can be tried from start to finish. The first expects the same body
	fields the demo form sends, so connecting it keeps every answer. The real list, and the search
	over it, will live in src/lib/flex, and the page will read from there instead.
*/
export const placeholderEndpoints: FlexEndpoint[] = [
	{
		method: 'POST',
		service: 'govuk_forms',
		url: '/app/forms/v1/submissions',
		description: 'Send a completed form',
		bodyFields: ['applicant_name', 'vessel_name', 'trainers']
	},
	{
		method: 'GET',
		service: 'govuk_forms',
		url: '/app/forms/v1/submissions/{{submission_id}}',
		description: 'Check whether a sent form has been processed'
	},
	{
		method: 'POST',
		service: 'govuk_forms',
		url: '/app/forms/v0/submit',
		description: 'Old way to send a form',
		bodyFields: ['form_data'],
		deprecated: true
	}
];
