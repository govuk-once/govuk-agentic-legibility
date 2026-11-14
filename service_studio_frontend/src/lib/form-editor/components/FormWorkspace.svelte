<script lang="ts">
	import type { ContextItem } from '$lib/components/context';
	import ProcessCanvas from '$lib/process-graph/ProcessCanvas.svelte';
	import StateCard from '$lib/process-graph/StateCard.svelte';
	import { describeState } from '$lib/process-graph/describe-state';
	import type { DraftSet } from '$lib/process-graph/drafts';
	import type { DeletedElements, NodePositions } from '$lib/process-graph/process-graph-types';
	import { processToGraph, stateTitle, visibleGraph } from '$lib/process-graph/process-to-graph';
	import { stateRows, targetOptions } from '$lib/process-graph/state-rows';
	import { questionBefore } from '$lib/schema/workflow/choice-answers';
	import { applyStateEdit } from '$lib/schema/workflow/edit-journey';
	import { descriptionOf } from '$lib/schema/workflow/edit-state';
	import { deleteFromJourney } from '$lib/schema/workflow/remove-state';
	import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
	import { formPaletteTools } from '../palette-tools';
	import { formDeveloperStateTypes, isEditableInForm } from '../schema/form-states';
	import { stateLabels, stateOutlineColours, stateTagColours } from '../state-labels';
	import DecisionEditCard from './DecisionEditCard.svelte';
	import DeveloperStateCard from './DeveloperStateCard.svelte';
	import StateEditCard from './StateEditCard.svelte';

	interface Props {
		process: WorkingProcess;
		// Shows the developer states and the error routes. Off, the graph and the list hold only the form's own steps.
		showDeveloperStates: boolean;
		// Where the person has dragged boxes to, and the call that records a drag. The page holds them, so they last
		// when the developer states are shown or hidden and this component is shown afresh.
		positions: NodePositions;
		onMoveNodes: (moved: NodePositions) => void;
		// The shapes placed from the palette that are not in the process yet, and the call that records a change to
		// them. The page holds them for the same reason as the positions.
		drafts: DraftSet;
		onChangeDrafts: (drafts: DraftSet) => void;
		// Called with the whole process after it is changed, so the page can keep the new copy.
		onChangeProcess: (process: WorkingProcess) => void;
		// The context added for the agent, by the code of the step it was added to, and the call that records a
		// change to the context of one step. The page holds it for the same reason as the positions.
		stepContext: Record<string, ContextItem[]>;
		onChangeStepContext: (code: string, items: ContextItem[]) => void;
	}

	let {
		process,
		showDeveloperStates,
		positions,
		onMoveNodes,
		drafts,
		onChangeDrafts,
		onChangeProcess,
		stepContext,
		onChangeStepContext
	}: Props = $props();

	// The graph is built once here and shared, so the canvas and the list always show the same titles and numbers.
	const graph = $derived(processToGraph(process, formDeveloperStateTypes));

	// What is shown with the developer states on or off. The list uses it, so it never offers a step that is not
	// on the graph.
	const shown = $derived(
		visibleGraph(graph, { showErrorRoutes: showDeveloperStates, showDeveloperSteps: showDeveloperStates })
	);
	const rows = $derived(stateRows(shown.nodes));

	// Every state a step could continue to, named for the list of choices on the edit card. It uses the whole graph
	// and not only what is shown, because a step can continue to a state that is hidden with the developer states.
	const targets = $derived(targetOptions(graph.nodes));

	// The state highlighted on the graph and in the list, and whether its card is open in place of the list. They
	// are held together so choosing a different state always closes a card that was left open.
	let selection = $state<{ code: string | null; open: boolean }>({ code: null, open: false });
	const selectedStateId = $derived(selection.code);

	/**
	 * Tells whether a state has a card of its own to open: a question, a message or a decision, which a person
	 * edits, or a state that a developer sets up, which is shown with its values as words. An end is only
	 * highlighted.
	 */
	function hasCard(state: WorkingState | undefined): boolean {
		return state !== undefined && state.state_type !== 'end';
	}

	/**
	 * Finds the question a decision follows, with the number and title it has in the list, for the decision card.
	 * There is none when the decision follows no single question, or the question is not a numbered step.
	 */
	function questionRowBefore(code: string) {
		const found = questionBefore(process, code);
		const row = found && rows.find((candidate) => candidate.stateId === found.code);
		return found && row ? { question: found.question, number: row.number, title: row.title } : undefined;
	}

	// Highlights a state without opening its card, which is what choosing a card in the list does.
	function highlight(code: string | null) {
		if (code !== selection.code) selection = { code, open: false };
	}

	// Highlights a state and opens its card when it has one, which is what choosing a box on the graph, the Edit
	// link of a card in the list, and adding a new step all do.
	function openCard(code: string | null) {
		selection = { code, open: code !== null && hasCard(process.states[code]) };
	}

	// The state whose card is open, with the row it has in the list when it is a numbered step.
	const openState = $derived(selection.open && selection.code ? process.states[selection.code] : undefined);
	const openRowIndex = $derived(rows.findIndex((row) => row.stateId === selection.code));

	// Why the last change could not be made, in words, shown over the canvas until it is dismissed. It is empty when
	// there is nothing to say. The canvas shows it and can add to it, so the two share it.
	let messages = $state<string[]>([]);

	/**
	 * Hands a changed process to the page. Any reason left over from an earlier change that could not be made is
	 * cleared first, because it no longer describes what is on the canvas.
	 */
	function applyChange(updated: WorkingProcess) {
		messages = [];
		onChangeProcess(updated);
	}

	// Takes states and lines out of the process, and drops the selection if the selected state went with them.
	function removeFromProcess(deleted: Pick<DeletedElements, 'stateCodes' | 'lines'>) {
		const result = deleteFromJourney(process, deleted);
		if (!result.ok) {
			messages = [result.reason];
			return;
		}
		applyChange(result.process);
		if (selectedStateId && !(selectedStateId in result.process.states)) highlight(null);
	}

	// Applies the edit card of a step or a decision and closes it, leaving it highlighted. The end is made in the
	// same change when the person chose that a step ends the journey.
	function applyEdit(code: string, updated: WorkingState, endsJourney = false) {
		applyChange(applyStateEdit(process, code, updated, endsJourney));
		selection = { code, open: false };
	}
</script>

<div class="form-workspace">
	<!-- Choosing a box or a diamond on the graph opens its card, and a step that has just been added opens its card
		too, ready for its words to be typed. -->
	<ProcessCanvas
		{process}
		{graph}
		paletteTools={formPaletteTools}
		connectedStepKind="input"
		showErrorRoutes={showDeveloperStates}
		showDeveloperSteps={showDeveloperStates}
		stepOutlineColours={stateOutlineColours}
		{positions}
		{onMoveNodes}
		{drafts}
		{onChangeDrafts}
		onChangeProcess={applyChange}
		bind:selectedStateId={() => selectedStateId, openCard}
		bind:messages
		onEditState={openCard}
		onDeleteStates={removeFromProcess}
	/>

	<aside class="form-workspace__panel" aria-label="Steps">
		{#if openState && selection.code && (openState.state_type === 'input' || openState.state_type === 'output') && openRowIndex >= 0}
			{@const code = selection.code}
			{@const row = rows[openRowIndex]}
			<!-- Shown afresh for each step, so what was typed for one step never carries over to another. -->
			{#key code}
				<StateEditCard
					currentState={openState}
					number={row.number}
					title={row.title}
					totalSteps={rows.length}
					targets={targets.filter((target) => target.stateId !== code)}
					canOpenPrevious={openRowIndex > 0}
					canOpenNext={openRowIndex < rows.length - 1}
					onOpenPrevious={() => openCard(rows[openRowIndex - 1].stateId)}
					onOpenNext={() => openCard(rows[openRowIndex + 1].stateId)}
					contextItems={stepContext[code] ?? []}
					onContextChange={(items) => onChangeStepContext(code, items)}
					onApply={(updated, endsJourney) => applyEdit(code, updated, endsJourney)}
					onCancel={() => (selection = { code, open: false })}
				/>
			{/key}
		{:else if openState && selection.code && openState.state_type === 'choice'}
			{@const code = selection.code}
			<!-- Shown afresh for each decision, so what was chosen for one never carries over to another. -->
			{#key code}
				<DecisionEditCard
					currentState={openState}
					title={stateTitle(openState, code)}
					before={questionRowBefore(code)}
					targets={targets.filter((target) => target.stateId !== code)}
					onApply={(updated) => applyEdit(code, updated)}
					onCancel={() => (selection = { code, open: false })}
				/>
			{/key}
		{:else if openState && selection.code && !isEditableInForm(openState)}
			{@const code = selection.code}
			<DeveloperStateCard
				title={stateTitle(openState, code)}
				tagLabel={stateLabels[openState.state_type]}
				tagColour={stateTagColours[openState.state_type]}
				facts={describeState(openState, code, () => undefined).facts}
				onClose={() => (selection = { code, open: false })}
			/>
		{:else}
			<div class="form-workspace__list">
				<div class="form-workspace__list-header">
					<h2 class="govuk-heading-s govuk-!-margin-bottom-0">Steps</h2>
					<p class="govuk-body-s govuk-!-margin-bottom-0 form-workspace__list-hint">
						{rows.length} steps · nothing selected
					</p>
				</div>

				{#each rows as row, index (row.stateId)}
					<StateCard
						stateId={row.stateId}
						number={row.number}
						title={row.title}
						description={descriptionOf(process.states[row.stateId])}
						tagLabel={stateLabels[row.stateType]}
						tagColour={stateTagColours[row.stateType]}
						selected={row.stateId === selectedStateId}
						canMoveUp={index > 0}
						canMoveDown={index < rows.length - 1}
						onSelect={highlight}
						onEdit={openCard}
					/>
				{/each}
			</div>

			<div class="form-workspace__panel-footer">
				<button class="govuk-button govuk-!-margin-bottom-0" type="button">Send to policy review</button>
			</div>
		{/if}
	</aside>
</div>

<style>
	.form-workspace {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	.form-workspace__panel {
		display: flex;
		flex-direction: column;
		flex: 0 0 400px;
		/* Without this, a flex item's automatic minimum size lets its content force the panel wider than its
			flex-basis instead of scrolling within it. */
		min-width: 0;
		min-height: 0;
		background-color: #ffffff;
		border-left: 1px solid #b1b4b6;
	}

	.form-workspace__list {
		flex: 1 1 auto;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
	}

	.form-workspace__list-header {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 18px 16px 14px;
		border-bottom: 1px solid #b1b4b6;
	}

	.form-workspace__list-hint {
		color: #505a5f;
	}

	.form-workspace__panel-footer {
		padding: 16px;
	}

	/* GOV.UK's own button is full width only below its tablet breakpoint, auto width above it. This panel is much
		narrower than that breakpoint even on a wide screen, so the button is told to stay full width of it. */
	.form-workspace__panel-footer .govuk-button {
		width: 100%;
	}

	@media (max-width: 900px) {
		.form-workspace {
			flex-direction: column;
		}

		.form-workspace__panel {
			flex-basis: auto;
			border-left: 0;
			border-top: 1px solid #b1b4b6;
		}
	}
</style>
