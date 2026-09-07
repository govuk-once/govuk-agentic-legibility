<script lang="ts">
	import StepDragHandle from './StepDragHandle.svelte';

	interface Props {
		number: number;
		title: string;
		description: string;
		tagLabel: string;
		/* Provides the colour name expected by the GOV.UK tag modifier so the supplied status receives the correct treatment. */
		tagColour: string;
		selected?: boolean;
	}

	let { number, title, description, tagLabel, tagColour, selected = false }: Props = $props();
</script>

<!-- A selected card mirrors graph selection without changing the step editing state. -->
<div class:step-card--selected={selected} class="step-card">
	<!-- The handle reserves a consistent drag target for the later ordering interaction. -->
	<StepDragHandle />
	<span class="step-card__number">{number}</span>
	<div class="step-card__summary">
		<h3 class="govuk-heading-s govuk-!-margin-bottom-1">{title}</h3>
		<p class="govuk-body govuk-!-margin-bottom-0">{description}</p>
	</div>
	<!-- Status uses the supplied GOV.UK colour modifier rather than local tag styling. -->
	<strong class="govuk-tag govuk-tag--{tagColour} step-card__tag">{tagLabel}</strong>
	<!-- Step actions remain separate from the summary so they keep fixed positions across rows. -->
	<a class="govuk-link step-card__edit" href="#top">Edit</a>
	<svg
		class="step-card__remove"
		width="14"
		height="14"
		viewBox="0 0 14 14"
		xmlns="http://www.w3.org/2000/svg"
		aria-hidden="true"
	>
		<path d="M2 2 L12 12 M12 2 L2 12" fill="none" stroke="#505a5f" stroke-width="1.6" />
	</svg>
</div>

<style>
	.step-card {
		display: flex;
		align-items: center;
		gap: 15px;
		padding: 15px 20px;
		background-color: #ffffff;
		border: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.step-card--selected {
		background-color: #e8f1f8;
		border-left: 5px solid #1d70b8;
	}

	.step-card__number {
		flex-shrink: 0;
		width: 20px;
		font-size: 1rem;
		font-weight: 700;
		color: #505a5f;
	}

	.step-card__summary {
		display: flex;
		flex-direction: column;
		flex-grow: 1;
		gap: 3px;
	}

	.step-card__tag {
		flex-shrink: 0;
	}

	.step-card__edit {
		flex-shrink: 0;
		font-size: 1rem;
	}

	.step-card__remove {
		flex-shrink: 0;
	}

	@media (max-width: 640px) {
		.step-card {
			align-items: flex-start;
			flex-wrap: wrap;
			padding: 15px;
		}

		.step-card__summary {
			min-width: 200px;
		}
	}
</style>
