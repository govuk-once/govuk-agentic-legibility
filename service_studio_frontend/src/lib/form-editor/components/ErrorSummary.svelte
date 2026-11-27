<script lang="ts">
	// The GOV.UK error summary, listing every problem at the top of a form with a link to the field it is about.
	// Nothing is shown when there are no problems.
	interface Problem {
		// The id of the field the problem is about, so its link moves to that field.
		fieldId: string;
		message: string;
	}

	interface Props {
		problems: Problem[];
		// The level of the summary's heading. A form on its own page uses 2, and a form inside a panel that sits under
		// a level 2 heading uses 3, so the headings stay in order.
		headingLevel?: 2 | 3;
	}

	let { problems, headingLevel = 2 }: Props = $props();
</script>

{#if problems.length > 0}
	<!-- Each new list of problems draws the summary again, so focus moves to it every time a form is sent with
		problems, as GOV.UK error summaries do, and a screen reader reads it out. -->
	{#key problems}
		<div class="govuk-error-summary" tabindex="-1" role="alert" {@attach (summary) => summary.focus()}>
			<svelte:element this={`h${headingLevel}`} class="govuk-error-summary__title">There is a problem</svelte:element>
			<div class="govuk-error-summary__body">
				<ul class="govuk-list govuk-error-summary__list">
					{#each problems as problem (problem.fieldId)}
						<li><a href="#{problem.fieldId}">{problem.message}</a></li>
					{/each}
				</ul>
			</div>
		</div>
	{/key}
{/if}
