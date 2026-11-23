<script lang="ts">
	import type { ContextItem } from '$lib/components/context';
	import ProcessCanvas from '$lib/process-graph/ProcessCanvas.svelte';
	import StateCard from '$lib/process-graph/StateCard.svelte';
	import { describeState } from '$lib/process-graph/describe-state';
	import type { DraftSet } from '$lib/process-graph/drafts';
	import type { DeletedElements, NodePositions } from '$lib/process-graph/process-graph-types';
	import { processToGraph, stateTitle, visibleGraph } from '$lib/process-graph/process-to-graph';
	import { stateRows, targetOptions } from '$lib/process-graph/state-rows';
	import { inputBefore, stateBefore } from '$lib/schema/workflow/choice-answers';
	import { applyStateEdit, canEndJourneyAt, endJourneyAt } from '$lib/schema/workflow/edit-journey';
	import { assignBefore, setStart } from '$lib/schema/workflow/edit-process';
	import { descriptionOf, hasNext } from '$lib/schema/workflow/edit-state';
	import { canMoveEarlier, canMoveLater, moveEarlier, moveLater } from '$lib/schema/workflow/move-state';
	import { deleteFromJourney } from '$lib/schema/workflow/remove-state';
	import { journeyErrors, journeyWarnings } from '$lib/schema/workflow/validate';
	import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
	import ModuleMenu from '$lib/modules/ModuleMenu.svelte';
	import { moduleCategories } from '$lib/modules/module-catalogue';
	import { isInModule, statesOfSameModule } from '$lib/modules/module-group';
	import { withRoutesForNewOptions } from '$lib/modules/option-routes';
	import { formPaletteTools } from '../palette-tools';
	import { formDeveloperStateTypes, formHiddenStateTypes, isEditableInForm } from '../schema/form-states';
	import { stateLabels, stateOutlineColours, stateTagColours } from '../state-labels';
	import DecisionEditCard from './DecisionEditCard.svelte';
	import DeveloperStateCard from './DeveloperStateCard.svelte';
	import JourneyCheckPanel from './JourneyCheckPanel.svelte';
	import StateEditCard from './StateEditCard.svelte';

	interface Props {
		process: WorkingProcess;
		// Shows the developer states and the error routes. Off, the graph and the list hold only the form's own steps.
		showDeveloperStates: boolean;
		// Where the person has dragged boxes to, and the call that records a drag. The page holds them, so they last
		// when the developer states are shown or hidden and this component is shown afresh.
		positions: NodePositions;
		onMoveNodes: (moved: NodePositions) => void;
		// How many times the graph has been arranged again, and the call that arranges it again.
		layoutRound: number;
		onRearrange: () => void;
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
		// Called when the form has passed its check and goes on to owner review. The page holds the whole form, so it
		// is the page that passes it on.
		onSendToOwnerReview: () => void;
	}

	let {
		process,
		showDeveloperStates,
		positions,
		onMoveNodes,
		layoutRound,
		onRearrange,
		drafts,
		onChangeDrafts,
		onChangeProcess,
		stepContext,
		onChangeStepContext,
		onSendToOwnerReview
	}: Props = $props();

	// The graph is built once here and shared, so the canvas and the list always show the same titles and numbers.
	const graph = $derived(processToGraph(process, formHiddenStateTypes));

	// What is shown with the developer states on or off. The list uses it, so it never offers a step that is not
	// on the graph.
	const shown = $derived(
		visibleGraph(graph, { showErrorRoutes: showDeveloperStates, showDeveloperSteps: showDeveloperStates })
	);
	const rows = $derived(stateRows(shown.nodes));

	// Every state a step could continue to, named for the list of choices on the edit card. It uses the whole graph
	// and not only what is shown, because a step can continue to a state that is hidden with the developer states.
	const targets = $derived(targetOptions(graph.nodes));

	// The name of each state as the lists of choices give it, so a problem names a state in the same words.
	const targetNames = $derived(new Map(targets.map((target) => [target.stateId, target.label])));

	// Whether the check before owner review is shown in place of the list of steps. While it is, the problems are
	// worked out again with every change, so a problem that is fixed leaves the list.
	let checking = $state(false);
	const errors = $derived(checking ? journeyErrors(process) : []);
	const warnings = $derived(checking ? journeyWarnings(process) : []);

	/**
	 * Checks the form before it is sent to owner review. A form with nothing to fix or finish goes straight on.
	 * Otherwise the problems are shown in the side panel.
	 */
	function sendToOwnerReview() {
		if (journeyErrors(process).length === 0 && journeyWarnings(process).length === 0) onSendToOwnerReview();
		else checking = true;
	}

	// The state highlighted on the graph and in the list, and whether its card is open in place of the list. They
	// are held together so choosing a different state always closes a card that was left open.
	let selection = $state<{ code: string | null; open: boolean }>({ code: null, open: false });
	const selectedStateId = $derived(selection.code);

	/**
	 * Tells whether a state has a card of its own to open: an input, a message or a decision, which a person
	 * edits, or a state that a developer sets up, which is shown with its values as words. An end is only
	 * highlighted.
	 */
	function hasCard(state: WorkingState | undefined): boolean {
		return state !== undefined && state.state_type !== 'end';
	}

	/**
	 * Finds the input a decision follows, with the number and title it has in the list, for the decision card.
	 * There is none when the decision follows no single input, or the input is not a numbered step.
	 */
	function inputRowBefore(code: string) {
		const found = inputBefore(process, code);
		const row = found && rows.find((candidate) => candidate.stateId === found.code);
		return found && row ? { input: found.input, number: row.number, title: row.title } : undefined;
	}

	// Finds the title of the developer step a decision follows, such as an API call, for the decision card.
	function developerStepBefore(code: string): string | undefined {
		const found = stateBefore(process, code);
		return found && formDeveloperStateTypes.includes(found.state.state_type) ? stateTitle(found.state, found.code) : undefined;
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
	// The row of the highlighted state, for the line under the heading of the list. A decision or an end has no row.
	const selectedRow = $derived(rows[openRowIndex]);

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

	/**
	 * Lists a state to take out together with the assign that goes with it. A form saves an answer with an assign
	 * placed straight before the next input or message. That assign is hidden with the developer states, so it is
	 * taken out with its step and is not left behind where the person cannot see it.
	 */
	function withAttachedAssign(code: string): string[] {
		const state = process.states[code];
		const attached = state && isEditableInForm(state) && hasNext(state) ? assignBefore(process, code) : undefined;
		return attached ? [attached, code] : [code];
	}

	// Takes states and lines out of the process, and drops the selection if the selected state went with them. A state
	// that came in with a module takes every other state of that copy of the module with it, so no part of a module
	// is left behind.
	function removeFromProcess(deleted: Pick<DeletedElements, 'stateCodes' | 'lines'>) {
		const withModules = deleted.stateCodes.flatMap((code) => statesOfSameModule(process, code));
		const stateCodes = [...new Set(withModules.flatMap(withAttachedAssign))];
		const result = deleteFromJourney(process, { stateCodes, lines: deleted.lines });
		if (!result.ok) {
			messages = [result.reason];
			return;
		}
		applyChange(result.process);
		if (selectedStateId && !(selectedStateId in result.process.states)) highlight(null);
	}

	// Takes one state out, which is what Remove on its card and the cross on its card in the list do.
	function removeState(code: string) {
		removeFromProcess({ stateCodes: [code], lines: [] });
	}

	// Makes a step the start of the journey and closes its card, because the card was opened before the change.
	function makeStart(code: string) {
		applyChange(setStart(process, code));
		selection = { code, open: false };
	}

	// Ends the journey at a step and closes its card, because the card still holds where the step went before.
	function endJourney(code: string) {
		const result = endJourneyAt(process, code);
		if (!result.ok) {
			messages = [result.reason];
			return;
		}
		applyChange(result.process);
		selection = { code, open: false };
	}

	// Moves a step up or down the journey, taking with it the assign that saves an answer before it. The graph is
	// arranged again, so the boxes follow the new order of the list.
	function moveStep(code: string, direction: 'up' | 'down') {
		applyChange((direction === 'up' ? moveEarlier : moveLater)(process, code, assignBefore));
		onRearrange();
	}

	// Applies the edit card of a step or a decision and closes it, leaving it highlighted. The end is made in the
	// same change when the person chose that a step ends the journey. An option added to the input of a module such
	// as the Choice decision also adds a way out to that module's decision.
	function applyEdit(code: string, updated: WorkingState, endsJourney = false) {
		applyChange(applyStateEdit(withRoutesForNewOptions(process, code, updated), code, updated, endsJourney));
		selection = { code, open: false };
	}
</script>

<div class="form-workspace">
	<ModuleMenu categories={moduleCategories} tools={formPaletteTools} />

	<div class="form-workspace__body">
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
			{layoutRound}
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
						onSetStart={process.start === code ? undefined : () => makeStart(code)}
						onEndJourney={canEndJourneyAt(process, code) ? () => endJourney(code) : undefined}
						onRemove={() => removeState(code)}
					/>
				{/key}
			{:else if openState && selection.code && openState.state_type === 'choice'}
				{@const code = selection.code}
				<!-- Shown afresh for each decision, so what was chosen for one never carries over to another. -->
				{#key code}
					<DecisionEditCard
						currentState={openState}
						title={stateTitle(openState, code)}
						before={inputRowBefore(code)}
						afterDeveloperStep={developerStepBefore(code)}
						targets={targets.filter((target) => target.stateId !== code)}
						onApply={(updated) => applyEdit(code, updated)}
						onCancel={() => (selection = { code, open: false })}
						onRemove={() => removeState(code)}
					/>
				{/key}
			{:else if openState && selection.code && !isEditableInForm(openState)}
				{@const code = selection.code}
				<DeveloperStateCard
					currentState={openState}
					title={stateTitle(openState, code)}
					tagLabel={stateLabels[openState.state_type]}
					tagColour={stateTagColours[openState.state_type]}
					facts={describeState(openState, code, () => undefined).facts}
					onClose={() => (selection = { code, open: false })}
				/>
			{:else if checking}
				<JourneyCheckPanel
					{errors}
					{warnings}
					nameOf={(code) => targetNames.get(code) ?? code}
					onSelect={highlight}
					onBack={() => (checking = false)}
					onContinue={onSendToOwnerReview}
				/>
			{:else}
				<div class="form-workspace__list">
					<div class="form-workspace__list-header">
						<h2 class="govuk-heading-s govuk-!-margin-bottom-0">Steps</h2>
						<p class="govuk-body-s govuk-!-margin-bottom-0 form-workspace__list-hint">
							{rows.length}
							{rows.length === 1 ? 'step' : 'steps'} · {selectedRow ? `step ${selectedRow.number} selected` : 'nothing selected'}
						</p>
					</div>

					{#each rows as row (row.stateId)}
						<StateCard
							stateId={row.stateId}
							number={row.number}
							title={row.title}
							description={descriptionOf(process.states[row.stateId])}
							tagLabel={stateLabels[row.stateType]}
							tagColour={stateTagColours[row.stateType]}
							selected={row.stateId === selectedStateId}
							canMoveUp={canMoveEarlier(process, row.stateId, assignBefore)}
							canMoveDown={canMoveLater(process, row.stateId, assignBefore)}
							onSelect={highlight}
							onEdit={openCard}
							onRemove={removeState}
							removeNoun={isInModule(process.states[row.stateId]) ? 'module' : 'step'}
							onMoveUp={(stateId) => moveStep(stateId, 'up')}
							onMoveDown={(stateId) => moveStep(stateId, 'down')}
						/>
					{/each}
				</div>

				<div class="form-workspace__panel-footer">
					<button class="govuk-button govuk-!-margin-bottom-0" type="button" onclick={sendToOwnerReview}>Send to owner review</button>
				</div>
			{/if}
		</aside>
	</div>
</div>

<style>
	/* The module menu runs across the top, over the canvas and the panel, which sit side by side below it. */
	.form-workspace {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-height: 0;
	}

	.form-workspace__body {
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
		.form-workspace__body {
			flex-direction: column;
		}

		.form-workspace__panel {
			flex-basis: auto;
			border-left: 0;
			border-top: 1px solid #b1b4b6;
		}
	}
</style>
