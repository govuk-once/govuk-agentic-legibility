<script lang="ts">
	import type { ProblemSeverity } from '$lib/schema/workflow/journey-problems';
	import type { JourneyProblem } from '$lib/schema/workflow/validate';

	/*
		The problems with the form, in a bar along the bottom of the editor that is always shown. Closed, the bar counts
		the errors and the warnings and names the first problem. Open, it lists every problem in a table, errors first,
		each with a link that highlights its step on the graph. Errors stop the form being sent to owner review and
		warnings do not, but the list itself never stops anything: it only shows what is found as the form changes.
	*/

	interface Props {
		// Every problem with how serious it is, errors first.
		problems: { problem: JourneyProblem; severity: ProblemSeverity }[];
		// The words that name a state: a label for the Step column, such as "Step 8", and the words of the link to it.
		placeOf: (code: string) => { label: string; linkText: string };
		onSelect: (code: string) => void;
	}

	let { problems, placeOf, onSelect }: Props = $props();

	const drawerId = $props.id();
	let open = $state(false);

	const errorCount = $derived(problems.filter((each) => each.severity === 'error').length);
	const warningCount = $derived(problems.length - errorCount);

	// The line shown in the closed bar: the first problem as a sentence, and how many more there are.
	const summary = $derived.by(() => {
		const [first] = problems;
		if (!first) return 'No problems found';
		const { problem } = first;
		const sentence = problem.state ? `${placeOf(problem.state).label} ${problem.message}` : problem.message;
		const more = problems.length - 1;
		return more === 0 ? sentence : `${sentence}, and ${more} more ${more === 1 ? 'problem' : 'problems'}`;
	});
</script>

<section class="problems-drawer" aria-label="Problems">
	<div class="problems-drawer__panel">
		<div class="problems-drawer__summary-bar">
			<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0 problems-drawer__toggle" aria-expanded={open} aria-controls={drawerId} onclick={() => (open = !open)}>
				{open ? 'Hide problems' : 'Show problems'}
			</button>

			<p class="govuk-body-s govuk-!-margin-bottom-0 problems-drawer__count">
				<span class="problem-count-box problem-count-box--error"><span class="problem-count-box__number">{errorCount}</span></span>
				<strong class="problems-drawer__count-label">{errorCount === 1 ? 'error' : 'errors'}</strong>
			</p>
			<p class="govuk-body-s govuk-!-margin-bottom-0 problems-drawer__count">
				<span class="problem-count-box problem-count-box--warning"><span class="problem-count-box__number">{warningCount}</span></span>
				<span class="problems-drawer__count-label">{warningCount === 1 ? 'warning' : 'warnings'}</span>
			</p>

			<p class="govuk-body-s govuk-!-margin-bottom-0 problems-drawer__note">
				{open ? 'Fix errors before you send this form for owner review. Warnings can wait.' : summary}
			</p>
		</div>

		<div id={drawerId} class="problems-drawer__list" hidden={!open}>
			{#if problems.length === 0}
				<p class="govuk-body-s govuk-!-margin-bottom-0">No problems found.</p>
			{:else}
				<table class="govuk-table govuk-!-font-size-16 govuk-!-margin-bottom-0 problems-drawer__table">
					<colgroup>
						<col class="problems-drawer__number-column" />
						<col class="problems-drawer__step-column" />
						<col class="problems-drawer__problem-column" />
						<col />
						<col class="problems-drawer__go-to-column" />
					</colgroup>
					<thead class="govuk-table__head">
						<tr class="govuk-table__row">
							<th scope="col" class="govuk-table__header problems-drawer__column-heading"><span class="govuk-visually-hidden">Number</span></th>
							<th scope="col" class="govuk-table__header problems-drawer__column-heading">Step</th>
							<th scope="col" class="govuk-table__header problems-drawer__column-heading">Problem</th>
							<th scope="col" class="govuk-table__header problems-drawer__column-heading">How to fix it</th>
							<th scope="col" class="govuk-table__header problems-drawer__column-heading"><span class="govuk-visually-hidden">Link to the step</span></th>
						</tr>
					</thead>
					<tbody class="govuk-table__body">
						{#each problems as { problem, severity }, index (index)}
							{@const place = problem.state ? placeOf(problem.state) : undefined}
							<tr class="govuk-table__row problems-drawer__row">
								<td class="govuk-table__cell">
									<span class="problem-count-box problem-count-box--{severity}"><span class="problem-count-box__number">{index + 1}</span></span>
									<span class="govuk-visually-hidden">{severity}</span>
								</td>
								<td class="govuk-table__cell govuk-!-font-weight-bold problems-drawer__text-cell">{place?.label ?? ''}</td>
								<td class="govuk-table__cell problems-drawer__text-cell">
									<span class="govuk-!-font-weight-bold">{problem.title}</span>
									<span class="problems-drawer__fix">{problem.fix}</span>
								</td>
								<td class="govuk-table__cell problems-drawer__text-cell problems-drawer__how-to-fix">{problem.howToFix ?? ''}</td>
								<td class="govuk-table__cell problems-drawer__text-cell problems-drawer__go-to">
									{#if problem.state && place}
										{@const code = problem.state}
										<a
											class="govuk-link govuk-!-font-weight-bold"
											href="#{code}"
											onclick={(event) => {
												event.preventDefault();
												onSelect(code);
											}}>{place.linkText}</a
										>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>
	</div>
</section>

<style>
	/* The widths of the first two columns of the table. The button that shows and hides the list takes up both, so
		the counts in the bar start where the Problem column starts and the two line up whether the list is open or
		closed. The height of the bar is the room the editor keeps for it at the bottom. */
	.problems-drawer {
		--problems-number-column-width: 50px;
		--problems-step-column-width: 180px;
		--problems-bar-height: 45px;
		position: relative;
		z-index: 10;
		flex: 0 0 var(--problems-bar-height);
	}

	/* The bar keeps its place at the bottom of the editor, and the list opens upwards over the graph and the side
		panel instead of pushing them up, so the editor keeps its size and the steps list and its button stay where
		they are, covered while the list is open. */
	.problems-drawer__panel {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: #ffffff;
		border-top: 1px solid #b1b4b6;
		box-shadow: 0 -5px 15px rgba(11, 12, 12, 0.07);
	}

	.problems-drawer__summary-bar {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		height: var(--problems-bar-height);
		padding: 0 25px;
	}

	/* A button that reads as a link, with a triangle drawn in CSS that points down when the list is open, in the
		same way as the summary of a GOV.UK details component. */
	.problems-drawer__toggle {
		position: relative;
		flex: 0 0 calc(var(--problems-number-column-width) + var(--problems-step-column-width));
		text-align: left;
		padding: 0 0 0 15px;
		background: none;
		border: 0;
		cursor: pointer;
	}

	.problems-drawer__toggle::before {
		content: '';
		position: absolute;
		top: 50%;
		left: 0;
		border-style: solid;
		border-color: transparent;
		border-width: 5px 0 5px 8px;
		border-left-color: currentColor;
		transform: translateY(-50%);
	}

	.problems-drawer__toggle[aria-expanded='true']::before {
		border-width: 8px 5px 0 5px;
		border-color: transparent;
		border-top-color: currentColor;
	}

	/* The GOV.UK font leaves more room below its letters than above them, so text centred in a box sits high. The text
		box of each count and the word beside it is trimmed to the height of its capital letters, so the browser
		centres the letters themselves and they line up with each other. A browser that does not support text-box yet
		centres the whole line, which leaves them about a pixel high but still level. The number has a span of its own
		because only a block of text can be trimmed, and the square round it is a flex box. */
	.problem-count-box__number,
	.problems-drawer__count-label {
		text-box: trim-both cap alphabetic;
	}

	.problems-drawer__count {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-right: 20px;
	}

	/* The note sits at the far end of the bar, after the counts. */
	.problems-drawer__note {
		margin-left: auto;
		color: #505a5f;
	}

	/* The list is held to a height that leaves the graph in view, and scrolls when there are more problems. */
	.problems-drawer__list {
		max-height: 300px;
		overflow-y: auto;
		padding: 0 25px 15px;
		border-top: 1px solid #b1b4b6;
	}

	/* Fixed column widths, so every row lines up with the bar above it however long its words are. */
	.problems-drawer__table {
		table-layout: fixed;
	}

	.problems-drawer__number-column {
		width: var(--problems-number-column-width);
	}

	.problems-drawer__step-column {
		width: var(--problems-step-column-width);
	}

	.problems-drawer__problem-column {
		width: 40%;
	}

	.problems-drawer__go-to-column {
		width: 240px;
	}

	/* Every cell of a problem is centred from top to bottom, so the step, the link and the number square line up
		with each other and with the middle of the problem's two lines. GOV.UK tables set cells to the top. */
	.problems-drawer__row > .govuk-table__cell {
		vertical-align: middle;
	}

	/* The cells that hold words are trimmed in the same way as the number squares, so their letters are centred and
		not the font's extra space. */
	.problems-drawer__text-cell {
		text-box: trim-both cap alphabetic;
	}

	.problems-drawer__column-heading {
		font-weight: 400;
		color: #505a5f;
	}

	.problems-drawer__fix {
		display: block;
		color: #505a5f;
	}

	.problems-drawer__how-to-fix {
		color: #505a5f;
	}

	.problems-drawer__go-to {
		text-align: right;
		white-space: nowrap;
	}

	/* A square number marker: red with white text for an error, yellow with black text for a warning. It is the same
		size as the numbered squares in the stage banner at the top of the editor. */
	.problem-count-box {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		width: 28px;
		height: 28px;
		font-size: 1rem;
		font-weight: 700;
	}

	.problem-count-box--error {
		background-color: #d4351c;
		color: #ffffff;
	}

	.problem-count-box--warning {
		background-color: #ffdd00;
		color: #0b0c0c;
	}
</style>
