<script lang="ts">
	import type { Snippet } from 'svelte';
	import { tick } from 'svelte';
	import type { StepValueProblem } from '../step-values/step-values';

	/*
		The form inside the panel of one developer step on the step values page. It holds the step's fields, lists what
		must be put right at the top, and has the button that marks the step as checked. Each kind of step gives its own
		fields and its own way of reading them.
	*/
	interface Props {
		// The step's title, read out with the button so a screen reader hears which step it marks.
		title: string;
		// Reads the fields when the button is pressed. It saves the step and gives no problems, or gives the problems
		// that stop it being saved.
		onmark: (fields: FormData) => StepValueProblem[];
		// The step's fields, given a way to find the problem with each field so it can be shown beside it.
		children: Snippet<[(field: string) => string | undefined]>;
	}

	let { title, onmark, children }: Props = $props();

	// The problems found when the button was last pressed, shown only after that.
	let problems = $state<StepValueProblem[]>([]);
	let errorSummary = $state<HTMLDivElement>();

	const problemFor = (field: string) => problems.find((problem) => problem.field === field)?.message;

	async function mark(event: SubmitEvent & { currentTarget: HTMLFormElement }) {
		event.preventDefault();
		problems = onmark(new FormData(event.currentTarget));
		if (problems.length > 0) {
			await tick();
			errorSummary?.focus();
		}
	}
</script>

{#if problems.length > 0}
	<div class="govuk-error-summary" bind:this={errorSummary} tabindex="-1" role="alert">
		<h3 class="govuk-error-summary__title">There is a problem</h3>
		<div class="govuk-error-summary__body">
			<ul class="govuk-list govuk-error-summary__list">
				{#each problems as problem (problem.field)}
					<li><a href="#{problem.field}">{problem.message}</a></li>
				{/each}
			</ul>
		</div>
	</div>
{/if}

<form novalidate onsubmit={mark}>
	{@render children(problemFor)}
	<button class="govuk-button govuk-!-margin-bottom-0" type="submit">
		Mark as checked<span class="govuk-visually-hidden">: {title}</span>
	</button>
</form>
