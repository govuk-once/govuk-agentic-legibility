<script lang="ts">
	import NodePalette, { type PaletteTool } from '$lib/graph-kit/NodePalette.svelte';
	import { addLooseStep, addStepBeforeStart, isNewStepKind, type NewStepKind } from '$lib/schema/workflow/edit-journey';
	import type { WorkingProcess } from '$lib/schema/workflow/working-process';
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
	} from './drafts';
	import ProcessGraph from './ProcessGraph.svelte';
	import type { DeletedElements, NodePositions, ProcessGraphElements, StepOutlineColours } from './process-graph-types';

	/*
		The palette, the graph and the message that explains a refused change, with everything the person can do
		on the canvas: drop a shape, draw a line, drag a line out to empty canvas and press Delete. Any editor of a
		process can use it. The editor supplies the panel beside it and decides how a state is edited or taken out.
	*/

	interface Props {
		process: WorkingProcess;
		// The nodes and edges of the process, built by the editor so its list of steps uses the same ones.
		graph: ProcessGraphElements;
		// The shapes the palette offers. The editor says which, so an editor that allows fewer shapes shows fewer.
		// The value of a box shape is the kind of step it adds, input or output. A decision, a start and an end are
		// told apart by their shape.
		paletteTools: PaletteTool[];
		// The kind of step added when a line is let go on empty canvas, where no shape was chosen from the palette.
		connectedStepKind: NewStepKind;
		showErrorRoutes: boolean;
		// Whether developer steps are drawn. It is on unless the editor turns it off.
		showDeveloperSteps?: boolean;
		// The colour of the outline of a box, for each kind of state the editor wants to tell apart. An editor that
		// gives none has the usual grey outline on every box.
		stepOutlineColours?: StepOutlineColours;
		// Where the person has dragged boxes to, and the call that records a drag.
		positions: NodePositions;
		onMoveNodes: (moved: NodePositions) => void;
		// The shapes placed from the palette that are not in the process yet, and the call that records a change to them.
		drafts: DraftSet;
		onChangeDrafts: (drafts: DraftSet) => void;
		// Called with the whole process after a change, so the editor can keep the new copy and clear old messages.
		onChangeProcess: (process: WorkingProcess) => void;
		// Called with the id of the process an invoke box runs, when the box is clicked.
		onOpenProcess?: (processId: string) => void;
		// The state highlighted on the graph, shared with the editor's list of steps. Null when nothing is selected.
		selectedStateId?: string | null;
		// Why the last change could not be made, in words. It is shared with the editor, because the editor's own
		// changes can be refused too. It is empty when there is nothing to say.
		messages?: string[];
		// Called with the code of a state that has just been added, so the editor can select it and open its form.
		onEditState: (code: string) => void;
		// Called with the states and lines that a press of Delete selected, which the editor takes out of the process.
		onDeleteStates: (deleted: Pick<DeletedElements, 'stateCodes' | 'lines'>) => void;
	}

	let {
		process,
		graph,
		paletteTools,
		connectedStepKind,
		showErrorRoutes,
		showDeveloperSteps = true,
		stepOutlineColours,
		positions,
		onMoveNodes,
		drafts,
		onChangeDrafts,
		onChangeProcess,
		onOpenProcess,
		selectedStateId = $bindable(null),
		messages = $bindable([]),
		onEditState,
		onDeleteStates
	}: Props = $props();

	/**
	 * Makes drafts that now have enough joined to them part of the process. The process to start from is given
	 * when it has just been changed and the editor has not caught up yet.
	 */
	function promote(set: DraftSet, base: WorkingProcess = process) {
		const promoted = promoteDrafts(base, set);
		if (promoted.process !== process) onChangeProcess(promoted.process);

		onChangeDrafts(promoted.set);
		if (promoted.reasons.length > 0) messages = promoted.reasons;
		// A decision that has just been made is shown with its form open, so its ways on can be set at once.
		else if (promoted.selectCode) onEditState(promoted.selectCode);
	}

	/**
	 * Draws a line the person has dragged between two shapes. A line between two things already in the process
	 * is made to the process at once. A line to or from a shape that is not in the process yet waits on the
	 * canvas until that shape is joined up enough to be added.
	 */
	function handleConnect(source: Endpoint, target: Endpoint) {
		if (source.kind !== 'draft' && target.kind !== 'draft') {
			const result = drawRealLine(process, source, target);
			if (result.ok) onChangeProcess(result.process);
			else messages = [result.reason];
			return;
		}
		promote(addDraftLine(drafts, source, target));
	}

	/**
	 * Adds what a shape dropped from the palette stands for. The shape is found among the ones the editor offers, so
	 * the canvas adds only what that editor allows. A box adds a step of the kind its value names. A decision, a
	 * start or an end is placed as a draft.
	 */
	function handleDropShape(value: string, position: { x: number; y: number }) {
		const tool = paletteTools.find((candidate) => candidate.value === value);
		if (!tool) return;

		if (tool.shape !== 'step') handleCreateDraft(tool.shape, position);
		else if (isNewStepKind(tool.value)) handleCreateStep(tool.value, position);
	}

	// Adds a new step where it was dropped. It is part of the process at once, with nothing after it, and its edit
	// form opens so the question and title can be typed.
	function handleCreateStep(kind: NewStepKind, position: { x: number; y: number }) {
		const added = addLooseStep(process, kind);
		onChangeProcess(added.process);

		onMoveNodes({ [added.code]: position });
		onEditState(added.code);
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
			const result = addStepBeforeStart(process, connectedStepKind);
			if (!result.ok || !result.code) return;

			onChangeProcess(result.process);
			onMoveNodes({ [result.code]: position });
			onEditState(result.code);
			return;
		}

		const added = addLooseStep(process, connectedStepKind);
		const joined = { kind: 'state', code: added.code } as const;
		if (source.kind === 'draft') {
			promote(addDraftLine(drafts, source, joined), added.process);
		} else {
			const drawn = drawRealLine(added.process, source, joined);
			if (!drawn.ok) {
				messages = [drawn.reason];
				return;
			}
			onChangeProcess(drawn.process);
		}

		onMoveNodes({ [added.code]: position });
		onEditState(added.code);
	}

	/**
	 * Takes out what a press of the Delete key selected. Draft shapes and lines only exist on the canvas, so
	 * they are removed from it. States and lines between states are handed to the editor to take out of the process.
	 */
	function handleDeleteElements(deleted: DeletedElements) {
		if (deleted.draftIds.length + deleted.draftLineIds.length > 0) {
			onChangeDrafts(removeFromDrafts(drafts, deleted.draftIds, deleted.draftLineIds));
		}
		if (deleted.stateCodes.length + deleted.lines.length === 0) return;

		onDeleteStates({ stateCodes: deleted.stateCodes, lines: deleted.lines });
	}
</script>

<NodePalette tools={paletteTools} />

<div class="process-canvas">
	<ProcessGraph
		{graph}
		{showErrorRoutes}
		{showDeveloperSteps}
		{stepOutlineColours}
		{positions}
		{onMoveNodes}
		{drafts}
		bind:selectedStateId
		{onOpenProcess}
		canConnect={(source, target) => canDraw(process, drafts, source, target)}
		onConnect={handleConnect}
		onCreateConnectedStep={handleCreateConnectedStep}
		onDropShape={handleDropShape}
		onDeleteElements={handleDeleteElements}
	/>

	{#if messages.length > 0}
		<div class="govuk-error-summary process-canvas__messages" role="alert">
			<h2 class="govuk-error-summary__title">That change was not made</h2>
			<div class="govuk-error-summary__body">
				<ul class="govuk-list govuk-error-summary__list">
					{#each messages as message, index (index)}
						<li>{message}</li>
					{/each}
				</ul>
				<button type="button" class="govuk-link process-canvas__dismiss" onclick={() => (messages = [])}>Dismiss</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.process-canvas {
		position: relative;
		flex: 1 1 auto;
		min-width: 0;
	}

	/* The reasons a change was refused sit on top of the canvas, so they are seen without moving the graph. */
	.process-canvas__messages {
		position: absolute;
		top: 15px;
		left: 15px;
		right: 15px;
		z-index: 5;
		margin: 0;
		background-color: #ffffff;
	}

	.process-canvas__dismiss {
		padding: 0;
		background: none;
		border: 0;
		font: inherit;
		cursor: pointer;
	}
</style>
