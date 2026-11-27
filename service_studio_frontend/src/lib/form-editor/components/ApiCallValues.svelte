<script lang="ts">
	import { resolve } from '$app/paths';
	import type { WorkingApiCall, WorkingState } from '$lib/schema/workflow/working-process';
	import { apiCallFields, apiCallMethods, apiCallValuesOf, apiCallWithValues, savedAnswerExample, type ApiCallValues } from '$lib/form-editor/step-values/api-call-values';
	import FieldError from '$lib/form-editor/components/FieldError.svelte';
	import StepValuesForm from '$lib/form-editor/components/StepValuesForm.svelte';
	import TechReviewButtons from '$lib/form-editor/components/TechReviewButtons.svelte';

	/*
		The panel of an API call step on the step values page: where it sends the request, what it sends, and where it
		saves the reply. What the call captures from the reply is shown but not changed here.
	*/
	interface Props {
		code: string;
		title: string;
		state: WorkingApiCall;
		// Saves the step with its checked values and marks it as checked.
		onchecked: (state: WorkingState) => void;
		// Closes the panel without saving.
		oncancel: () => void;
	}

	let { code, title, state, onchecked, oncancel }: Props = $props();

	const values = $derived(apiCallValuesOf(state));
	const captures = $derived(Object.entries(state.capture ?? {}));
	// A saved answer from this call's own body, which the hint under the body uses as its example.
	const example = $derived(savedAnswerExample(state.body));

	/**
	 * Reads the typed values into the call and saves it when they pass their checks.
	 */
	function mark(fields: FormData) {
		const read = (field: keyof ApiCallValues) => String(fields.get(field) ?? '');
		const result = apiCallWithValues(state, {
			url: read('url'),
			method: read('method'),
			service: read('service'),
			assign: read('assign'),
			body: read('body')
		});
		if (!result.ok) return result.problems;
		onchecked(result.state);
		return [];
	}
</script>

<StepValuesForm {title} onmark={mark} {oncancel}>
	{#snippet children(problemFor)}
		<div class="govuk-grid-row">
			<div class="govuk-grid-column-one-half">
				<div class="govuk-form-group" class:govuk-form-group--error={problemFor(apiCallFields.url)}>
					<label class="govuk-label govuk-label--s" for={apiCallFields.url}>Url</label>
					<FieldError field={apiCallFields.url} message={problemFor(apiCallFields.url)} />
					<input
						class="govuk-input schema-value"
						class:govuk-input--error={problemFor(apiCallFields.url)}
						id={apiCallFields.url}
						name="url"
						type="text"
						spellcheck="false"
						aria-describedby={problemFor(apiCallFields.url) ? `${apiCallFields.url}-error` : undefined}
						value={values.url}
					/>
					<a class="govuk-link govuk-!-display-inline-block govuk-!-margin-top-1" href={resolve('/tech-review/form/(steps)/flex/[step]', { step: code })}>
						Choose a different endpoint
					</a>
				</div>

				<div class="govuk-form-group">
					<TechReviewButtons
						legend="Method"
						id={apiCallFields.method}
						name="method"
						options={apiCallMethods.map((method) => ({ value: method, label: method }))}
						value={values.method}
					/>
				</div>

				<div class="govuk-form-group" class:govuk-form-group--error={problemFor(apiCallFields.service)}>
					<label class="govuk-label govuk-label--s" for={apiCallFields.service}>Service</label>
					<FieldError field={apiCallFields.service} message={problemFor(apiCallFields.service)} />
					<input
						class="govuk-input govuk-input--width-20 schema-value"
						class:govuk-input--error={problemFor(apiCallFields.service)}
						id={apiCallFields.service}
						name="service"
						type="text"
						spellcheck="false"
						aria-describedby={problemFor(apiCallFields.service) ? `${apiCallFields.service}-error` : undefined}
						value={values.service}
					/>
				</div>

				<div class="govuk-form-group">
					<div class="api-call-values__reply">
						<div class:govuk-form-group--error={problemFor(apiCallFields.assign)}>
							<label class="govuk-label govuk-label--s" for={apiCallFields.assign}>Save reply as (assign)</label>
							<FieldError field={apiCallFields.assign} message={problemFor(apiCallFields.assign)} />
							<input
								class="govuk-input govuk-input--width-10 schema-value"
								class:govuk-input--error={problemFor(apiCallFields.assign)}
								id={apiCallFields.assign}
								name="assign"
								type="text"
								spellcheck="false"
								aria-describedby="api-call-reply-hint{problemFor(apiCallFields.assign) ? ` ${apiCallFields.assign}-error` : ''}"
								value={values.assign}
							/>
						</div>
						<div>
							<h4 class="govuk-label govuk-label--s">Capture</h4>
							{#if captures.length > 0}
								<ul class="govuk-list govuk-!-margin-bottom-0">
									{#each captures as [variable, from] (variable)}
										<li class="schema-value">{variable} from {typeof from === 'string' ? from : from.from}</li>
									{/each}
								</ul>
							{:else}
								<p class="govuk-body govuk-!-margin-bottom-0">Not set</p>
							{/if}
						</div>
					</div>
					<p class="govuk-hint govuk-!-margin-top-2 govuk-!-margin-bottom-0" id="api-call-reply-hint">
						Set at least one of these, or no later step can use the reply.
					</p>
				</div>
			</div>

			<div class="govuk-grid-column-one-half">
				<div class="govuk-form-group" class:govuk-form-group--error={problemFor(apiCallFields.body)}>
					<label class="govuk-label govuk-label--s" for={apiCallFields.body}>Body</label>
					<FieldError field={apiCallFields.body} message={problemFor(apiCallFields.body)} />
					<textarea
						class="govuk-textarea schema-value govuk-!-margin-bottom-2"
						class:govuk-textarea--error={problemFor(apiCallFields.body)}
						id={apiCallFields.body}
						name="body"
						rows="14"
						spellcheck="false"
						aria-describedby="api-call-body-hint{problemFor(apiCallFields.body) ? ` ${apiCallFields.body}-error` : ''}"
						value={values.body}
					></textarea>
					<p class="govuk-hint govuk-!-margin-bottom-0" id="api-call-body-hint">
						{#if example}
							Values written as {example.value} are saved answers from earlier steps.
						{:else}
							Values written with "$" and a name are saved answers from earlier steps.
						{/if}
						Leave it empty when the call sends no body.
					</p>
				</div>
			</div>
		</div>
	{/snippet}
</StepValuesForm>

<style>
	/* Where the reply is saved and what is captured from it sit side by side, as they work together. */
	.api-call-values__reply {
		display: flex;
		flex-wrap: wrap;
		gap: 20px;
	}
</style>
