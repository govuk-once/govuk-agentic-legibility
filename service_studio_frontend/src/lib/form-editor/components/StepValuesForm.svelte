<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { StepValueProblem } from '../step-values/step-values';
	import ErrorSummary from './ErrorSummary.svelte';

	/*
		The form inside the panel of one developer step on the step values page. It holds the step's fields, lists what
		must be put right at the top, and has the button that marks the step as checked and a link that closes the panel
		without saving. Each kind of step gives its own fields and its own way of reading them.
	*/
	interface Props {
		// The step's title, read out with the button so a screen reader hears which step it marks.
		title: string;
		// Reads the fields when the button is pressed. It saves the step and gives no problems, or gives the problems
		// that stop it being saved.
		onmark: (fields: FormData) => StepValueProblem[];
		// Closes the panel without saving anything typed in it.
		oncancel: () => void;
		// The step's fields, given a way to find the problem with each field so it can be shown beside it.
		children: Snippet<[(field: string) => string | undefined]>;
	}

	let { title, onmark, oncancel, children }: Props = $props();

	// The problems found when the button was last pressed, shown only after that.
	let problems = $state<StepValueProblem[]>([]);

	const problemFor = (field: string) => problems.find((problem) => problem.field === field)?.message;

	function mark(event: SubmitEvent & { currentTarget: HTMLFormElement }) {
		event.preventDefault();
		problems = onmark(new FormData(event.currentTarget));
	}
</script>

<!-- The fields of each step use the field's name as their id. -->
<ErrorSummary problems={problems.map((problem) => ({ fieldId: problem.field, message: problem.message }))} headingLevel={3} />

<form novalidate onsubmit={mark}>
	{@render children(problemFor)}
	<div class="govuk-button-group govuk-!-margin-bottom-0">
		<button class="govuk-button" type="submit">
			Mark as checked<span class="govuk-visually-hidden">: {title}</span>
		</button>
		<button class="govuk-link" type="button" onclick={oncancel}>
			Cancel<span class="govuk-visually-hidden">: {title}</span>
		</button>
	</div>
</form>
