<script lang="ts">
	import { placeholderWaitDuration } from '$lib/schema/workflow/placeholders';
	import type { WorkingState } from '$lib/schema/workflow/working-process';
	import { typedDurationInWords, waitDurationField, waitDurationText, waitWithDuration } from '../step-values/wait-values';
	import FieldError from './FieldError.svelte';
	import StepValuesForm from './StepValuesForm.svelte';

	/*
		The panel of a wait step on the step values page. A wait has one value, how long it waits.
	*/
	interface Props {
		title: string;
		state: Extract<WorkingState, { state_type: 'wait' }>;
		// Saves the step with its checked duration and marks it as checked.
		onchecked: (state: WorkingState) => void;
		// Closes the panel without saving.
		oncancel: () => void;
	}

	let { title, state, onchecked, oncancel }: Props = $props();

	// The duration as it is typed, so the line beside it can say in words how long that is.
	let duration = $derived(waitDurationText(state));

	/**
	 * Reads the typed duration into the wait and saves it when it is a duration or the name of a saved value.
	 */
	function mark(fields: FormData) {
		const result = waitWithDuration(state, String(fields.get('duration') ?? ''));
		if (!result.ok) return result.problems;
		onchecked(result.state);
		return [];
	}
</script>

<StepValuesForm {title} onmark={mark} {oncancel}>
	{#snippet children(problemFor)}
		{@const problem = problemFor(waitDurationField)}
		{@const inWords = typedDurationInWords(duration)}
		<div class="govuk-form-group" class:govuk-form-group--error={problem}>
			<label class="govuk-label govuk-label--s" for={waitDurationField}>Duration</label>
			<FieldError field={waitDurationField} message={problem} />
			<div class="wait-values__field">
				<input
					class="govuk-input govuk-input--width-10 wait-values__code"
					class:govuk-input--error={problem}
					id={waitDurationField}
					name="duration"
					type="text"
					spellcheck="false"
					aria-describedby="wait-duration-hint{problem ? ` ${waitDurationField}-error` : ''}"
					value={duration}
					oninput={(event) => (duration = event.currentTarget.value)}
				/>
				<p class="govuk-hint govuk-!-margin-bottom-0" id="wait-duration-hint">
					{#if inWords}{inWords}.{/if}
					Use the name of a saved value such as wait_time to set it from an earlier answer. A step changed into a wait starts at
					{placeholderWaitDuration}.
				</p>
			</div>
		</div>
	{/snippet}
</StepValuesForm>

<style>
	/* The duration is written as it is in the schema, so it is set in a fixed width font. */
	.wait-values__code {
		font-family: ui-monospace, Menlo, Consolas, monospace;
		font-size: 1rem;
	}

	/* The field and the line that says how long it is sit side by side, and wrap on a narrow screen. */
	.wait-values__field {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		gap: 15px 30px;
	}

	.wait-values__field .govuk-hint {
		max-width: 400px;
	}
</style>
