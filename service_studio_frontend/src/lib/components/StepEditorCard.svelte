<script lang="ts">
	import StepDragHandle from './StepDragHandle.svelte';

	interface Props {
		number: number;
		title: string;
		description: string;
		selected?: boolean;
	}

	let { number, title, description, selected = false }: Props = $props();
	// The component identifier keeps label targets unique when more than one step is open for editing.
	const componentId = $props.id();
</script>

<!-- The expanded card replaces one summary row while preserving its position in the step list. -->
<div class:step-editor--selected={selected} class="step-editor">
	<!-- The header repeats the step identity so the open form remains tied to its journey position. -->
	<div class="step-editor__header">
		<StepDragHandle />
		<span class="step-editor__number">{number}</span>
		<div class="step-editor__summary">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-1">{title}</h3>
			<p class="govuk-body govuk-!-margin-bottom-0">{description}</p>
		</div>
		<strong class="govuk-tag govuk-tag--yellow step-editor__tag">Editing</strong>
	</div>

	<!-- Form controls use unique identifiers so labels remain correct when several editors are rendered. -->
	<div class="step-editor__form">
		<div class="govuk-form-group step-editor__form-group">
			<label class="govuk-label govuk-label--s" for="{componentId}-step-title">Step title</label>
			<input
				class="govuk-input step-editor__title-input"
				id="{componentId}-step-title"
				name="step-title"
				type="text"
				value={title}
			/>
		</div>

		<div class="step-editor__select-row">
			<div class="govuk-form-group step-editor__form-group">
				<label class="govuk-label govuk-label--s" for="{componentId}-answer-type">Answer type</label>
				<select class="govuk-select" id="{componentId}-answer-type" name="answer-type">
					<option selected>Question group</option>
				</select>
			</div>
			<div class="govuk-form-group step-editor__form-group">
				<label class="govuk-label govuk-label--s" for="{componentId}-branches-to">Branches to</label>
				<select class="govuk-select" id="{componentId}-branches-to" name="branches-to">
					<option selected>Step 4 · unless bypassed</option>
				</select>
			</div>
		</div>

		<div class="step-editor__actions">
			<button class="govuk-button step-editor__apply" type="button">Apply changes</button>
			<a class="govuk-link" href="#top">Discard</a>
			<a class="govuk-link step-editor__remove" href="#top">Remove step</a>
		</div>
	</div>
</div>

<style>
	.step-editor {
		background-color: #ffffff;
		border: 3px solid #1d70b8;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.step-editor--selected {
		background-color: #e8f1f8;
	}

	.step-editor__header {
		display: flex;
		align-items: center;
		gap: 15px;
		padding: 15px;
	}

	.step-editor__number {
		flex-shrink: 0;
		width: 20px;
		font-size: 1rem;
		font-weight: 700;
		color: #505a5f;
	}

	.step-editor__summary {
		display: flex;
		flex-direction: column;
		flex-grow: 1;
		gap: 3px;
	}

	.step-editor__tag {
		flex-shrink: 0;
	}

	.step-editor__form {
		display: flex;
		flex-direction: column;
		gap: 15px;
		padding: 5px 15px 20px 50px;
	}

	.step-editor__form-group {
		margin-bottom: 0;
	}

	.step-editor__title-input {
		max-width: 420px;
	}

	.step-editor__select-row {
		display: flex;
		gap: 25px;
	}

	.step-editor__actions {
		display: flex;
		align-items: center;
		gap: 20px;
		margin-top: 5px;
	}

	.step-editor__apply {
		margin-bottom: 0;
	}

	.step-editor__remove {
		color: #d4351c;
	}

	.step-editor__remove:visited {
		color: #d4351c;
	}

	@media (max-width: 640px) {
		.step-editor__header,
		.step-editor__select-row,
		.step-editor__actions {
			align-items: flex-start;
			flex-wrap: wrap;
		}

		.step-editor__summary {
			min-width: 200px;
		}

		.step-editor__form {
			padding: 5px 15px 20px;
		}
	}
</style>
