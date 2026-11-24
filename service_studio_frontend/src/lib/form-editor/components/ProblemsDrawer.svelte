<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { ProblemSeverity } from '$lib/schema/workflow/journey-problems';
	import type { JourneyProblem } from '$lib/schema/workflow/validate';
	import { fixPictures } from '../fix-pictures';
	import HowToFixPicture from './HowToFixPicture.svelte';

	/*
		The problems with the form, in a bar along the bottom of the editor that is always shown. Closed, the bar counts
		the errors and the warnings. Open, it lists every problem in a table, errors first,
		each with a link that highlights its step on the graph. Errors stop the form being sent to owner review and
		warnings do not, but the list itself never stops anything: it only shows what is found as the form changes.
	*/

	interface Props {
		// Every problem with how serious it is, errors first.
		problems: { problem: JourneyProblem; severity: ProblemSeverity }[];
		// The words that name a state: a label for the Step column, such as "Step 8", and the words of the link to it.
		placeOf: (code: string) => { label: string; linkText: string };
		onSelect: (code: string) => void;
		// What the editor puts at the far end of the bar, such as the button that sends the form on, so it sits next to
		// the counts that decide whether it can be used.
		actions?: Snippet;
	}

	let { problems, placeOf, onSelect, actions }: Props = $props();

	const drawerId = $props.id();
	let open = $state(false);

	const errorCount = $derived(problems.filter((each) => each.severity === 'error').length);
	const warningCount = $derived(problems.length - errorCount);

	// How many problems the open list shows before it scrolls, so it never covers most of the graph.
	const rowsBeforeScrolling = 4;

	// The height the list is held to, in pixels, or nothing while there are no more problems than that.
	let listHeight = $state<number>();

	/**
	 * Measures where the last row before scrolling ends, so the list is held to that height. Rows are not all the same
	 * height, because a fix can take one, two or three lines, so the height is measured and not fixed. It is measured
	 * again whenever the table changes size, such as when a problem is fixed or the window is resized.
	 */
	function holdToFirstRows(table: HTMLTableElement) {
		const measure = () => {
			const lastShown = table.tBodies[0]?.rows[rowsBeforeScrolling - 1];
			const hasMore = (table.tBodies[0]?.rows.length ?? 0) > rowsBeforeScrolling;
			listHeight = lastShown && hasMore ? lastShown.offsetTop + lastShown.offsetHeight : undefined;
		};
		const observer = new ResizeObserver(measure);
		observer.observe(table);
		return () => {
			observer.disconnect();
			listHeight = undefined;
		};
	}
</script>

<section class="problems-drawer" aria-label="Problems">
	<div class="problems-drawer__panel" class:problems-drawer__panel--open={open}>
		<div class="problems-drawer__summary-bar">
			<button type="button" class="govuk-link govuk-!-font-size-19 problems-drawer__toggle" aria-expanded={open} aria-controls={drawerId} onclick={() => (open = !open)}>
				{open ? 'Hide problems' : 'Show problems'}
			</button>

			<p class="govuk-body govuk-!-margin-bottom-0 problems-drawer__count">
				<span class="problem-count-box problem-count-box--error"><span class="problem-count-box__number">{errorCount}</span></span>
				<strong class="problems-drawer__count-label">{errorCount === 1 ? 'Error' : 'Errors'}</strong>
			</p>
			<p class="govuk-body govuk-!-margin-bottom-0 problems-drawer__count">
				<span class="problem-count-box problem-count-box--warning"><span class="problem-count-box__number">{warningCount}</span></span>
				<span class="problems-drawer__count-label">{warningCount === 1 ? 'Warning' : 'Warnings'}</span>
			</p>

			{#if actions}
				<div class="problems-drawer__actions">
					{@render actions()}
				</div>
			{/if}
		</div>

		<div id={drawerId} class="problems-drawer__list" hidden={!open} style:max-height={listHeight === undefined ? undefined : `${listHeight}px`}>
			{#if problems.length === 0}
				<p class="govuk-body-s govuk-!-margin-bottom-0">No problems found.</p>
			{:else}
				<table class="govuk-table govuk-!-font-size-16 govuk-!-margin-bottom-0 problems-drawer__table" {@attach holdToFirstRows}>
					<colgroup>
						<col class="problems-drawer__number-column" />
						<col class="problems-drawer__step-column" />
						<col />
						<col class="problems-drawer__how-to-fix-column" />
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
							{@const picture = fixPictures[problem.kind]}
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
								<td class="govuk-table__cell problems-drawer__text-cell problems-drawer__how-to-fix">
									{#if picture}
										<HowToFixPicture {picture} />
									{:else}
										{problem.howToFix ?? ''}
									{/if}
								</td>
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
	/* The widths of the first two columns of the table, and the height of the bar. The button that shows and hides
		the list is as wide as the first two columns together. */
	.problems-drawer {
		--problems-number-column-width: 50px;
		--problems-step-column-width: 180px;
		--problems-bar-height: 69px;
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
	}

	/* While the list is open it lies over the graph, so a soft shadow along its top edge lifts it off the graph. The
		negative spread keeps the shadow to the top edge, so none of it falls on the side panel beside the console. */
	.problems-drawer__panel--open {
		box-shadow: 0 -10px 15px -10px rgba(11, 12, 12, 0.15);
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

	/* The GOV.UK font leaves more room below its letters than above them. The text box of each count and the word
		beside it is trimmed to the height of its capital letters, so the browser centres the letters themselves and
		not that extra room. A browser that does not support text-box yet centres the whole line. The number has a span
		of its own because only a block of text can be trimmed, and the square round it is a flex box. */
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

	/* The editor's actions sit at the far end of the bar. */
	.problems-drawer__actions {
		display: flex;
		align-items: center;
		gap: 15px;
		margin-left: auto;
	}

	/* The list scrolls once it holds more problems than it shows. Its height is measured from the rows, so it is set
		on the content alone, and the padding below the rows sits outside it. */
	.problems-drawer__list {
		box-sizing: content-box;
		overflow-y: auto;
		padding: 0 25px 15px;
		border-top: 1px solid #b1b4b6;
	}

	/* The columns keep the widths they are given, however long the words in them are. */
	.problems-drawer__table {
		table-layout: fixed;
	}

	.problems-drawer__number-column {
		width: var(--problems-number-column-width);
	}

	.problems-drawer__step-column {
		width: var(--problems-step-column-width);
	}

	/* Wide enough for a before and after picture. The Problem column takes the room that is left. */
	.problems-drawer__how-to-fix-column {
		width: 210px;
	}

	.problems-drawer__go-to-column {
		width: 240px;
	}

	/* Every cell of a problem is centred from top to bottom. GOV.UK tables set cells to the top. */
	.problems-drawer__row > .govuk-table__cell {
		vertical-align: middle;
	}

	/* The cells that hold words are trimmed in the same way as the number squares, so their letters are centred and
		not the font's extra space. */
	.problems-drawer__text-cell {
		text-box: trim-both cap alphabetic;
	}

	/* The column headings stay in view while the list scrolls under them. */
	.problems-drawer__column-heading {
		position: sticky;
		top: 0;
		z-index: 1;
		font-weight: 400;
		color: #505a5f;
		background-color: #ffffff;
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
