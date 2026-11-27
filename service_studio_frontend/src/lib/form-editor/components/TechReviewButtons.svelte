<script lang="ts">
	/*
		A row of joined buttons for picking one value, such as the method of an API call. Each button is a radio input
		with its label drawn as the button, so it is read out and used with the keyboard as a set of radios. An option
		that cannot be picked is greyed out.

		GOV.UK has no joined buttons, so this has its own class, tech-review-buttons. It is an agreed exception to using
		GOV.UK classes only.
	*/
	interface Props {
		legend: string;
		// The id of the first radio input, which an error summary links to.
		id: string;
		// The name of the radio inputs, which is the name a form reads the picked value by.
		name: string;
		options: { value: string; label: string; disabled?: boolean }[];
		// The option picked when the buttons are first shown.
		value: string;
	}

	let { legend, id, name, options, value }: Props = $props();

	// The option picked now. It starts as the given one and changes as another is picked, and the form reads it from
	// the radio inputs.
	let selected = $derived(value);
</script>

<fieldset class="govuk-fieldset">
	<legend class="govuk-fieldset__legend govuk-fieldset__legend--s">{legend}</legend>
	<div class="tech-review-buttons">
		{#each options as option, index (option.value)}
			<label
				class="tech-review-buttons__option"
				class:tech-review-buttons__option--selected={option.value === selected}
				class:tech-review-buttons__option--disabled={option.disabled}
			>
				<input
					class="tech-review-buttons__input"
					id={index === 0 ? id : undefined}
					type="radio"
					{name}
					value={option.value}
					checked={option.value === selected}
					disabled={option.disabled}
					onchange={() => (selected = option.value)}
				/>
				{option.label}
			</label>
		{/each}
	</div>
</fieldset>

<style>
	/* The options touch, so the row reads as one control. A row that wraps on a narrow screen keeps a gap between
		its lines. */
	.tech-review-buttons {
		display: flex;
		flex-wrap: wrap;
		row-gap: 10px;
	}

	/* Each option after the first is pulled over the border of the one before, so neighbours share one border. */
	.tech-review-buttons__option + .tech-review-buttons__option {
		margin-left: -2px;
	}

	/* Each option looks like a button with a black outline, and the picked one is filled black. */
	.tech-review-buttons__option {
		position: relative;
		padding: 10px;
		font-family: 'GDS Transport', arial, sans-serif;
		font-size: 1rem;
		line-height: 1.25;
		color: #0b0c0c;
		background-color: #ffffff;
		border: 2px solid #0b0c0c;
		cursor: pointer;
	}

	/* The picked option is drawn above its neighbours, so its border is not hidden under theirs. */
	.tech-review-buttons__option--selected {
		z-index: 1;
		color: #ffffff;
		background-color: #0b0c0c;
	}

	.tech-review-buttons__option--disabled {
		color: #505a5f;
		border-color: #b1b4b6;
		cursor: not-allowed;
	}

	/* The radio itself is hidden from sight but kept for the keyboard and screen readers, so the focus is drawn on the
		label instead, in the GOV.UK focus colour. */
	.tech-review-buttons__input {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}

	.tech-review-buttons__option:has(.tech-review-buttons__input:focus-visible) {
		outline: 3px solid #ffdd00;
		outline-offset: 0;
		box-shadow: inset 0 0 0 2px #0b0c0c;
	}
</style>
