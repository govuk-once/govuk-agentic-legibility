<script lang="ts">
	import type { WorkingState } from '$lib/schema/workflow/working-process';
	import {
		assignKindLabels,
		assignLinesOf,
		assignPartField,
		assignVariableField,
		assignWithLines,
		type AssignKind
	} from '../step-values/assign-values';
	import FieldError from './FieldError.svelte';
	import StepValuesForm from './StepValuesForm.svelte';
	import TechReviewButtons from './TechReviewButtons.svelte';

	/*
		The panel of an assign step on the step values page. Each variable the step sets has its own block: the kind of
		value, which is shown but cannot be changed, the variable's name, and the parts of its value.
	*/
	interface Props {
		title: string;
		state: Extract<WorkingState, { state_type: 'assign' }>;
		// Saves the step with its checked values and marks it as checked.
		onchecked: (state: WorkingState) => void;
		// Closes the panel without saving.
		oncancel: () => void;
	}

	let { title, state, onchecked, oncancel }: Props = $props();

	const lines = $derived(assignLinesOf(state));

	// Every kind of value as a button, with all but the line's own kind greyed out.
	const kindOptions = (own: AssignKind) =>
		Object.entries(assignKindLabels).map(([kind, label]) => ({ value: kind, label, disabled: kind !== own }));

	/**
	 * Reads the typed names and parts of every line into the assign and saves it when they pass their checks.
	 */
	function mark(fields: FormData) {
		const typed = lines.map((line, index) => ({
			variable: String(fields.get(assignVariableField(index)) ?? ''),
			parts: line.parts.map((_, part) => String(fields.get(assignPartField(index, part)) ?? ''))
		}));
		const result = assignWithLines(state, typed);
		if (!result.ok) return result.problems;
		onchecked(result.state);
		return [];
	}
</script>

<StepValuesForm {title} onmark={mark} {oncancel}>
	{#snippet children(problemFor)}
		{#each lines as line, index (index)}
			<div class="govuk-form-group">
				<TechReviewButtons
					legend="Kind of value"
					id="assign-{index}-kind"
					name="assign-{index}-kind"
					options={kindOptions(line.kind)}
					value={line.kind}
				/>
			</div>

			<div class="assign-values__fields govuk-!-margin-bottom-6">
				{@render textField(assignVariableField(index), 'Variable to set', line.variable, problemFor)}
				{#each line.parts as part, partIndex (part.name)}
					{@render textField(assignPartField(index, partIndex), part.label, part.text, problemFor)}
				{/each}
			</div>
		{/each}
	{/snippet}
</StepValuesForm>

<!-- One named field of the panel, with its problem above it. -->
{#snippet textField(id: string, label: string, value: string, problemFor: (field: string) => string | undefined)}
	{@const problem = problemFor(id)}
	<div class="govuk-form-group govuk-!-margin-bottom-0" class:govuk-form-group--error={problem}>
		<label class="govuk-label govuk-label--s" for={id}>{label}</label>
		<FieldError field={id} message={problem} />
		<input
			class="govuk-input assign-values__code"
			class:govuk-input--error={problem}
			{id}
			name={id}
			type="text"
			spellcheck="false"
			aria-describedby={problem ? `${id}-error` : undefined}
			{value}
		/>
	</div>
{/snippet}

<style>
	/* The variable and the parts of its value sit side by side, and wrap onto more lines on a narrow screen. */
	.assign-values__fields {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 20px;
	}

	/* Variable names and values are written as they are in the schema, so they are set in a fixed width font. */
	.assign-values__code {
		font-family: ui-monospace, Menlo, Consolas, monospace;
		font-size: 1rem;
	}
</style>
