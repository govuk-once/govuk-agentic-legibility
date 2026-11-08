<script lang="ts">
	import ProcessGraph from '$lib/service-editor/graph/ProcessGraph.svelte';
	import NodePalette, { type PaletteTool } from '$lib/graph-kit/NodePalette.svelte';
	import { describeState } from '$lib/service-editor/graph/describe-state';
	import {
		addDraft,
		addDraftLine,
		canDraw,
		drawRealLine,
		newDraftId,
		promoteDrafts,
		removeFromDrafts,
		type DraftKind,
		type DraftSet,
		type Endpoint
	} from '$lib/service-editor/graph/drafts';
	import { isErrorKind } from '$lib/schema/workflow/routes';
	import { processToGraph, stateTitle, visibleGraph } from '$lib/service-editor/graph/process-to-graph';
	import { stateRows, targetOptions } from '$lib/service-editor/graph/state-rows';
	import type { DeletedElements, NodePositions } from '$lib/service-editor/graph/process-graph-types';
	import { addLooseStep, addStepBeforeStart, endJourneyAt } from '$lib/schema/workflow/edit-journey';
	import { removeUnreachableStates, setStart } from '$lib/schema/workflow/edit-process';
	import { hasNext, replaceState } from '$lib/schema/workflow/edit-state';
	import { reachableInOrder } from '$lib/schema/workflow/journey-order';
	import { canMoveEarlier, canMoveLater, moveEarlier, moveLater } from '$lib/schema/workflow/move-state';
	import { deleteFromJourney } from '$lib/schema/workflow/remove-state';
	import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';
	import StateDetails from './StateDetails.svelte';
	import StateList from './StateList.svelte';

	interface Props {
		process: WorkingProcess;
		showErrorRoutes: boolean;
		// Where the person has dragged boxes to, and the call that records a drag. The page holds them, so
		// they last while the page is open even after another process has been shown and this one comes back.
		positions: NodePositions;
		onMoveNodes: (moved: NodePositions) => void;
		// The shapes placed from the palette that are not in the process yet, and the call that records a change
		// to them. The page holds them for the same reason as the positions.
		drafts: DraftSet;
		onChangeDrafts: (drafts: DraftSet) => void;
		// Called with the whole process after one of its states is changed, so the page can keep the new copy.
		onChangeProcess: (process: WorkingProcess) => void;
		// Called with the id of the process an invoke box runs, when the box is clicked.
		onOpenProcess: (processId: string) => void;
	}

	let { process, showErrorRoutes, positions, onMoveNodes, drafts, onChangeDrafts, onChangeProcess, onOpenProcess }: Props = $props();

	// The shapes the palette offers: a step, a decision, a start and an end.
	const paletteTools: PaletteTool[] = [
		{ value: 'step', label: 'Step', shape: 'step' },
		{ value: 'condition', label: 'Decision', shape: 'condition' },
		{ value: 'start', label: 'Start', shape: 'start' },
		{ value: 'end', label: 'End', shape: 'end' }
	];

	// The graph is built once here and shared, so the canvas and the list always show the same titles and
	// numbers.
	const graph = $derived(processToGraph(process));
	// What is shown with the error routes on or off. The list and the details use it, so they never offer
	// a step that is not on the graph.
	const shown = $derived(visibleGraph(graph, showErrorRoutes));

	// Every state a route could lead to, named for the lists of choices in the edit form. It uses the whole graph
	// and not only what is shown, because a route can lead to a state that is hidden with the error routes.
	const targets = $derived(targetOptions(graph.nodes));

	// Every state that can be reached from the start by some route, error routes included. A state that is not
	// here can never run, which is worth telling the person after a change leaves one behind.
	const reachable = $derived(new Set(reachableInOrder(process)));

	// Why the last change could not be made, in words, shown over the canvas until it is dismissed. It is empty when
	// there is nothing to say.
	let messages = $state<string[]>([]);

	/**
	 * Hands a changed process to the page. Any reason left over from an earlier change that could not be made is
	 * cleared first, because it no longer describes what is on the canvas.
	 */
	function applyChange(updated: WorkingProcess) {
		messages = [];
		onChangeProcess(updated);
	}

	// The state highlighted on the graph and in the list, and whether its edit form is open. They are held
	// together so choosing a different state always closes a form that was left open, and so a step that has just
	// been added can open straight into its form, ready for its question and title to be typed. The page shows this component
	// afresh for each process, so nothing is selected when a different process is opened.
	let selection = $state<{ code: string | null; editing: boolean }>({ code: null, editing: false });
	const selectedStateId = $derived(selection.code);

	// Highlights a state, or nothing. Choosing the state that is already highlighted leaves its form as it was.
	function select(code: string | null) {
		if (code !== selection.code) selection = { code, editing: false };
	}

	// Selects a state and opens its edit form, ready for the person to type the question and title.
	function selectAndEdit(code: string) {
		selection = { code, editing: true };
	}

	/**
	 * Makes drafts that now have enough joined to them part of the process. The process to start from is given
	 * when it has just been changed and the page has not caught up yet.
	 */
	function promote(set: DraftSet, base: WorkingProcess = process) {
		const promoted = promoteDrafts(base, set);
		if (promoted.process !== process) applyChange(promoted.process);

		onChangeDrafts(promoted.set);
		if (promoted.reasons.length > 0) messages = promoted.reasons;
		// A decision that has just been made is shown with its form open, so its ways on can be set at once.
		else if (promoted.selectCode) selectAndEdit(promoted.selectCode);
	}

	/**
	 * Draws a line the person has dragged between two shapes. A line between two things already in the process
	 * is made to the process at once. A line to or from a shape that is not in the process yet waits on the
	 * canvas until that shape is joined up enough to be added.
	 */
	function handleConnect(source: Endpoint, target: Endpoint) {
		if (source.kind !== 'draft' && target.kind !== 'draft') {
			const result = drawRealLine(process, source, target);
			if (result.ok) applyChange(result.process);
			else messages = [result.reason];
			return;
		}
		promote(addDraftLine(drafts, source, target));
	}

	// Adds a new step where it was dropped. It is part of the process at once, with nothing after it, and its edit
	// form opens so the question and title can be typed.
	function handleCreateStep(position: { x: number; y: number }) {
		const added = addLooseStep(process);
		applyChange(added.process);

		onMoveNodes({ [added.code]: position });
		selectAndEdit(added.code);
	}

	// Places a decision, start or end on the canvas where it was dropped. It stays a draft until enough is joined to it,
	// because none of the three can be part of the process on its own.
	function handleCreateDraft(kind: DraftKind, position: { x: number; y: number }) {
		onChangeDrafts(addDraft(drafts, { id: newDraftId(), kind, position }));
	}

	// A line let go on empty canvas adds a new step there, joined to the shape the line came from. From the start
	// dot the new step becomes the start. From a decision that is still a draft, the line waits for the decision
	// to be joined up.
	function handleCreateConnectedStep(source: Endpoint, position: { x: number; y: number }) {
		if (source.kind === 'start') {
			const result = addStepBeforeStart(process);
			if (!result.ok || !result.code) return;

			applyChange(result.process);
			onMoveNodes({ [result.code]: position });
			selectAndEdit(result.code);
			return;
		}

		const added = addLooseStep(process);
		const joined = { kind: 'state', code: added.code } as const;
		if (source.kind === 'draft') {
			promote(addDraftLine(drafts, source, joined), added.process);
		} else {
			const drawn = drawRealLine(added.process, source, joined);
			if (!drawn.ok) {
				messages = [drawn.reason];
				return;
			}
			applyChange(drawn.process);
		}

		onMoveNodes({ [added.code]: position });
		selectAndEdit(added.code);
	}

	/**
	 * Takes out what a press of the Delete key selected. Draft shapes and lines only exist on the canvas, so
	 * they are removed from it. States and lines between states are taken out of the process.
	 */
	function handleDeleteElements(deleted: DeletedElements) {
		if (deleted.draftIds.length + deleted.draftLineIds.length > 0) {
			onChangeDrafts(removeFromDrafts(drafts, deleted.draftIds, deleted.draftLineIds));
		}
		if (deleted.stateCodes.length + deleted.lines.length === 0) return;

		removeFromProcess(deleted);
	}

	// Takes states and lines out of the process, and drops the selection if the selected state went with them.
	function removeFromProcess(deleted: Pick<DeletedElements, 'stateCodes' | 'lines'>) {
		const result = deleteFromJourney(process, deleted);
		if (!result.ok) {
			messages = [result.reason];
			return;
		}
		applyChange(result.process);
		if (selectedStateId && !(selectedStateId in result.process.states)) select(null);
	}

	// Applies the edit form for a state. When the person chose that the state ends the journey, the end is made in
	// the same change, because a second change would start from a process that does not have the edit yet. An end
	// that only this state led to is taken out when the state stops leading to it, as it is when a line is drawn
	// from the state to somewhere else. Nothing else it used to lead to is taken out.
	function applyEdit(code: string, updated: WorkingState, endsJourney: boolean) {
		const edited = replaceState(process, code, updated);
		const ended = endsJourney ? endJourneyAt(edited, code) : undefined;

		const before = process.states[code];
		const oldNext = before && hasNext(before) ? before.next : undefined;
		const leftEnd = oldNext !== undefined && process.states[oldNext]?.type === 'end' ? [oldNext] : [];
		applyChange(removeUnreachableStates(ended?.ok ? ended.process : edited, leftEnd));
	}

	// Ends the journey at a state, which is the End the journey here action in the edit form.
	function handleEndJourney(code: string) {
		const result = endJourneyAt(process, code);
		if (result.ok) applyChange(result.process);
		else messages = [result.reason];
	}

	// Tells whether the journey can be ended at a state: it continues to a single next state that is not already an end, or it has not been joined to anything yet.
	function canEndAt(code: string): boolean {
		const state = process.states[code];
		return state !== undefined && hasNext(state) && (state.next === undefined || process.states[state.next]?.type !== 'end');
	}

	// The title of a state in this process, or nothing when no state has that code. The panel uses it to
	// name each state that a route leads to.
	function titleOf(code: string): string | undefined {
		const state = process.states[code];
		return state ? stateTitle(state, code) : undefined;
	}

	// The selected state for the panel. A state that is hidden, because only an error route leads to it,
	// has no details to show until the error routes are shown again.
	const selectedState = $derived(
		selectedStateId && shown.nodes.some((node) => node.id === selectedStateId) ? process.states[selectedStateId] : undefined
	);

	// The selected state in words. While the error routes are hidden on the graph they are left out here
	// too, so the panel never points to a step that is not shown.
	const description = $derived.by(() => {
		if (!selectedStateId || !selectedState) return undefined;
		const described = describeState(selectedState, selectedStateId, titleOf);
		return { ...described, routes: described.routes.filter((route) => showErrorRoutes || !isErrorKind(route.kind)) };
	});
</script>

<div class="process-workspace">
	<NodePalette tools={paletteTools} />

	<div class="process-workspace__canvas">
		<ProcessGraph
			{graph}
			{showErrorRoutes}
			{positions}
			{onMoveNodes}
			{drafts}
			bind:selectedStateId={() => selectedStateId, select}
			{onOpenProcess}
			canConnect={(source, target) => canDraw(process, drafts, source, target)}
			onConnect={handleConnect}
			onCreateConnectedStep={handleCreateConnectedStep}
			onCreateStep={handleCreateStep}
			onCreateDraft={handleCreateDraft}
			onDeleteElements={handleDeleteElements}
		/>

		{#if messages.length > 0}
			<div class="govuk-error-summary process-workspace__messages" role="alert">
				<h2 class="govuk-error-summary__title">That change was not made</h2>
				<div class="govuk-error-summary__body">
					<ul class="govuk-list govuk-error-summary__list">
						{#each messages as message, index (index)}
							<li>{message}</li>
						{/each}
					</ul>
					<button type="button" class="govuk-link process-workspace__dismiss" onclick={() => (messages = [])}>Dismiss</button>
				</div>
			</div>
		{/if}
	</div>

	<aside class="process-workspace__panel" aria-label="Steps">
		<div class="process-workspace__list">
			<StateList rows={stateRows(shown.nodes)} bind:selectedStateId={() => selectedStateId, select} />
		</div>

		{#if selectedStateId && selectedState && description}
			{@const code = selectedStateId}
			<div class="process-workspace__details">
				<!-- Shown afresh for each state, so an open edit form never carries over to another state. -->
				{#key selectedStateId}
					<StateDetails
						title={titleOf(code) ?? code}
						{description}
						currentState={selectedState}
						{targets}
						unreachable={!reachable.has(code)}
						canMoveUp={canMoveEarlier(process, code)}
						canMoveDown={canMoveLater(process, code)}
						onMove={(direction) => applyChange((direction === 'up' ? moveEarlier : moveLater)(process, code))}
						isStart={process.start === code}
						canEnd={canEndAt(code)}
						onSetStart={() => applyChange(setStart(process, code))}
						onEndJourney={() => handleEndJourney(code)}
						onRemove={() => removeFromProcess({ stateCodes: [code], lines: [] })}
						onApply={(updated: WorkingState, endsJourney: boolean) => applyEdit(code, updated, endsJourney)}
						onSelectState={(stateId) => {
							// A route to a state that does not exist has nothing to show.
							if (process.states[stateId]) select(stateId);
						}}
						{onOpenProcess}
						onClose={() => select(null)}
						editing={selection.editing && selection.code === code}
						onEditingChange={(editing) => (selection = { code, editing })}
					/>
				{/key}
			</div>
		{/if}
	</aside>
</div>

<style>
	.process-workspace {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	.process-workspace__canvas {
		position: relative;
		flex: 1 1 auto;
		min-width: 0;
	}

	/* The reasons a change was refused sit on top of the canvas, so they are seen without moving the graph. */
	.process-workspace__messages {
		position: absolute;
		top: 15px;
		left: 15px;
		right: 15px;
		z-index: 5;
		margin: 0;
		background-color: #ffffff;
	}

	.process-workspace__dismiss {
		padding: 0;
		background: none;
		border: 0;
		font: inherit;
		cursor: pointer;
	}

	/* The list of states keeps the space it needs and scrolls on its own. When a state is selected its
		details take up to half of the panel below it and scroll on their own too, so the highlighted row
		stays in view. */
	.process-workspace__panel {
		display: flex;
		flex-direction: column;
		flex: 0 0 400px;
		min-width: 0;
		min-height: 0;
		background-color: #ffffff;
		border-left: 1px solid #b1b4b6;
	}

	.process-workspace__list {
		flex: 1 1 0;
		min-height: 0;
		overflow-y: auto;
	}

	.process-workspace__details {
		flex: 0 1 55%;
		min-height: 0;
		overflow-y: auto;
		border-top: 1px solid #b1b4b6;
	}

	@media (max-width: 900px) {
		.process-workspace {
			flex-direction: column;
		}

		.process-workspace__panel {
			flex-basis: auto;
			border-left: 0;
			border-top: 1px solid #b1b4b6;
		}
	}
</style>
