<script lang="ts">
	import { untrack } from 'svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import Progress from '$lib/components/Progress.svelte';
	import StepCard from '$lib/components/StepCard.svelte';
	import StepEditorCard from '$lib/components/StepEditorCard.svelte';
	import JourneyGraph from '$lib/graph/JourneyGraph.svelte';
	import GraphToolbar from '$lib/graph/GraphToolbar.svelte';
	import type { ContextItem } from '$lib/components/context';
	import { humanKind, isBranchStep, kindColour } from '$lib/schema';
	import type { Service, ServiceStep } from '$lib/schema';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const stages = [
		{ number: 1, label: 'Start', state: 'complete' as const },
		{ number: 2, label: 'Create', state: 'complete' as const },
		{ number: 3, label: 'Edit and review', state: 'current' as const },
		{ number: 4, label: 'Policy check', state: 'upcoming' as const },
		{ number: 5, label: 'Publish', state: 'upcoming' as const }
	];

	// The editable copy of the service being worked on. It uses raw state because every change below
	// replaces the whole object rather than editing it in place. untrack marks this as a one off read of
	// the starting data, the effect further down is what keeps this copy up to date if the person picks
	// a different service without leaving the page.
	let workingService = $state.raw<Service>(untrack(() => structuredClone(data.example.service)));

	/**
	 * Every step that already had no transitions when a service was loaded, so the graph can tell those
	 * genuine, already saved endings apart from a step that only just became a dead end as the side effect
	 * of something else in this editing session, such as being dropped on the canvas or wired into a
	 * branch but not yet given anywhere further to go.
	 */
	function deadEndsAtLoad(service: Service): Set<string> {
		return new Set(service.steps.filter((step) => step.transitions.length === 0).map((step) => step.id));
	}

	// Grows as the person explicitly decides a step ends the journey, from the step editor's own "End the
	// journey here", from wiring a draft End shape into a step, or from deleting a gateway, so any of those
	// count as deliberate from then on too, the same as one that was already a genuine ending on load.
	let explicitEndStepIds = $state<Set<string>>(untrack(() => deadEndsAtLoad(data.example.service)));

	function markExplicitEnd(stepId: string) {
		explicitEndStepIds = new Set([...explicitEndStepIds, stepId]);
	}

	// Context added for the agent, by step id. Held here only to try out the interaction: it lasts while
	// the page is open, is not part of the service, and is not saved anywhere.
	let stepContext = $state.raw<Record<string, ContextItem[]>>({});

	function handleContextChange(stepId: string, items: ContextItem[]) {
		stepContext = { ...stepContext, [stepId]: items };
	}

	// Tracks which step is highlighted. Shared both ways with the graph, so selecting a step in the list
	// also highlights it on the canvas, and the other way round.
	let selectedStepId = $state<string | null>(null);
	// Which step, if any, is open for editing. Kept separate from selectedStepId so selecting a step,
	// whether from the list or the graph, only ever highlights it rather than forcing its editor open.
	let editingStepId = $state<string | null>(null);
	// Owned here, rather than inside JourneyGraph, because the design's own toolbar controlling it sits
	// above the whole editor body, not scoped to the canvas column alone.
	let showBranching = $state(true);
	// The graph component instance, so a step created interactively, by dragging from the toolbar or
	// dragging a connection out to empty canvas, can be told where on the canvas to appear the moment it is
	// created, before the graph's own reconciliation would otherwise have to guess.
	let journeyGraph: ReturnType<typeof JourneyGraph> | undefined = $state();

	// Counted from the working copy, so the toolbar's stats always match what is actually on the canvas.
	const branchCount = $derived(workingService.steps.filter(isBranchStep).length);

	// Loads a fresh copy of the working service whenever the page moves to a different one, for example
	// using the browser's back or forward buttons to switch between two services without a full page
	// reload. This is needed because SvelteKit keeps reusing this same page rather than starting it
	// fresh every time only the service named in the URL changes. Only runs when the service has
	// actually changed, so it does not fire on every unrelated update.
	let loadedSlug = untrack(() => data.example.slug);
	$effect(() => {
		if (data.example.slug === loadedSlug) return;
		loadedSlug = data.example.slug;
		workingService = structuredClone(data.example.service);
		explicitEndStepIds = deadEndsAtLoad(workingService);
		stepContext = {};
		editingStepId = null;
		selectedStepId = null;
	});

	// The single place a step number is worked out, from its position in the list, so it can never go out
	// of step after an add, remove or reorder.
	const stepsWithNumbers = $derived(workingService.steps.map((step, index) => ({ ...step, number: index + 1 })));

	// Closes whichever editor is open as soon as a different step becomes highlighted. This covers every
	// way the highlighted step can change, a click in the list, a click on the graph, or clicking Edit
	// somewhere else, all in one place rather than repeating the same check in each handler. It never
	// closes the editor for the step actually being edited, because handleEdit always highlights and
	// opens the same step together.
	$effect(() => {
		if (editingStepId && editingStepId !== selectedStepId) {
			editingStepId = null;
		}
	});

	function handleSelect(stepId: string) {
		selectedStepId = stepId;
	}

	function handleEdit(stepId: string) {
		editingStepId = stepId;
		selectedStepId = stepId;
	}

	function handleCancelEdit(stepId: string) {
		if (editingStepId === stepId) {
			editingStepId = null;
		}
	}

	function handleApplyStep(updatedStep: ServiceStep) {
		workingService = {
			...workingService,
			steps: workingService.steps.map((step) => (step.id === updatedStep.id ? updatedStep : step))
		};
		// Choosing "Ends the journey" from the step's own "Continues to" field is just as deliberate a
		// decision as the dedicated End action, so it counts the same way.
		if (updatedStep.transitions.length === 0) markExplicitEnd(updatedStep.id);
		editingStepId = null;
	}

	/**
	 * Removes a step from the service once its removal has been confirmed by the card itself. Also drops
	 * any transition that pointed at the removed step, and moves the journey entry point to the new first
	 * step if the entry step itself was removed, so the working copy stays close to valid.
	 */
	function handleRemoveStep(stepId: string) {
		const steps = workingService.steps
			.filter((step) => step.id !== stepId)
			.map((step) => ({
				...step,
				transitions: step.transitions.filter((transition) => transition.targetStepId !== stepId)
			}));
		const startStepId =
			workingService.startStepId === stepId ? (steps[0]?.id ?? workingService.startStepId) : workingService.startStepId;

		// A step left with no transitions here had its own only route removed along with the step it led
		// to, which is deliberate in the same way the End action is: the person just chose to remove the
		// very thing that step continued to.
		for (const step of workingService.steps) {
			if (step.id === stepId) continue;
			const hadRoute = step.transitions.some((t) => t.targetStepId === stepId);
			const stillHasRoutes = steps.find((candidate) => candidate.id === step.id)?.transitions.length;
			if (hadRoute && !stillHasRoutes) markExplicitEnd(step.id);
		}

		workingService = { ...workingService, startStepId, steps };
		if (selectedStepId === stepId) selectedStepId = null;
		if (editingStepId === stepId) editingStepId = null;
	}

	/**
	 * Removes every step that has become unreachable starting from the given ids: not just a step an edit
	 * directly stopped pointing at, but any further step that was only reachable through it, so ending a
	 * branch never leaves a dangling private chain of steps behind that nothing points to any more and
	 * the canvas has nowhere sensible to draw. A step that anything else still transitions to, or the
	 * journey's own start step, is left alone even if it was in the given ids.
	 */
	function removeUnreachableSteps(service: Service, fromIds: string[]): Service {
		let steps = service.steps;
		const toCheck = [...fromIds];

		while (toCheck.length > 0) {
			const id = toCheck.pop()!;
			if (id === service.startStepId) continue;

			const stillReferenced = steps.some((step) => step.transitions.some((t) => t.targetStepId === id));
			if (stillReferenced) continue;

			const orphan = steps.find((step) => step.id === id);
			if (!orphan) continue;

			steps = steps.filter((step) => step.id !== id);
			toCheck.push(...orphan.transitions.map((t) => t.targetStepId));
		}

		return steps === service.steps ? service : { ...service, steps };
	}

	/**
	 * Swaps a step with its neighbour in the given direction, reordering the service step list so both
	 * the list and the graph pick up the new sequence. Order is presentational only: ids drive the
	 * transitions and the layout, so a swap cannot break the routing.
	 */
	function handleMoveStep(stepId: string, direction: 'up' | 'down') {
		const index = workingService.steps.findIndex((step) => step.id === stepId);
		if (index === -1) return;

		const targetIndex = direction === 'up' ? index - 1 : index + 1;
		if (targetIndex < 0 || targetIndex >= workingService.steps.length) return;

		const reordered = [...workingService.steps];
		[reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
		workingService = { ...workingService, steps: reordered };
	}

	/**
	 * Moves editing focus to the step immediately before or after the one currently open, by list
	 * position, rather than reordering anything. This is what the step editor's own up/down arrows do:
	 * StepCard's arrows in the list already cover reordering a step's position, so the same shaped
	 * control here instead steps through the journey, taking both the editor and the graph's highlight to
	 * the adjacent step in one action.
	 */
	function handleEditAdjacentStep(stepId: string, direction: 'up' | 'down') {
		const index = stepsWithNumbers.findIndex((step) => step.id === stepId);
		if (index === -1) return;

		const targetIndex = direction === 'up' ? index - 1 : index + 1;
		const target = stepsWithNumbers[targetIndex];
		if (!target) return;

		handleEdit(target.id);
	}

	/**
	 * Builds a fresh, unconnected step ready to drop onto the canvas. Every interactive way of adding a
	 * step, dragging the toolbar's own Step item, or dragging a connection out to empty canvas, starts from
	 * this same shape and then wires it in its own way.
	 */
	function newBlankStep(): ServiceStep {
		return {
			id: crypto.randomUUID(),
			type: { kind: 'info', body: '' },
			name: 'New step',
			description: 'Not yet configured',
			fields: [],
			transitions: []
		};
	}

	/**
	 * Drops a new, unconnected step at the given canvas position, from dragging the toolbar's Step item
	 * onto the canvas. placeNextNodeAt is called first so the graph's own reconciliation already knows
	 * where to put the node the moment this change reaches it, rather than falling back to a guess.
	 */
	function handleCreateStep(position: { x: number; y: number }) {
		const newStep = newBlankStep();
		journeyGraph?.placeNextNodeAt(newStep.id, position);
		workingService = { ...workingService, steps: [...workingService.steps, newStep] };
		editingStepId = newStep.id;
		selectedStepId = newStep.id;
	}

	/**
	 * Creates a new step and wires it as a fresh onward route from sourceStepId, from dragging a connection
	 * out from a node's own handle to empty canvas rather than onto another node. The sentinel 'start'
	 * stands for the journey's own entry terminal: dragging from there makes the new step the journey's
	 * entry point instead, ahead of whatever step led it before, mirroring what happens for a real step.
	 */
	function handleCreateConnectedStep(sourceStepId: string, position: { x: number; y: number }) {
		const newStep = newBlankStep();
		journeyGraph?.placeNextNodeAt(newStep.id, position);

		if (sourceStepId === 'start') {
			newStep.transitions = [{ targetStepId: workingService.startStepId }];
			workingService = {
				...workingService,
				startStepId: newStep.id,
				steps: [newStep, ...workingService.steps]
			};
			editingStepId = newStep.id;
			selectedStepId = newStep.id;
			return;
		}

		const sourceStep = workingService.steps.find((step) => step.id === sourceStepId);
		if (!sourceStep) return;

		const steps = workingService.steps.map((step) =>
			step.id === sourceStepId
				? { ...step, transitions: [...step.transitions, { targetStepId: newStep.id }] }
				: step
		);
		workingService = { ...workingService, steps: [...steps, newStep] };
		editingStepId = newStep.id;
		selectedStepId = newStep.id;
	}

	/**
	 * Adds a real transition between two existing steps, from dragging a connection between them on the
	 * canvas. The sentinel 'start' stands for the journey's own entry terminal, so connecting from there
	 * reassigns which step the journey begins at rather than adding a transition to a step named 'start'.
	 * A route that already exists between the two is left alone rather than duplicated.
	 */
	function handleConnectSteps(sourceStepId: string, targetStepId: string) {
		if (sourceStepId === 'start') {
			workingService = { ...workingService, startStepId: targetStepId };
			return;
		}

		const sourceStep = workingService.steps.find((step) => step.id === sourceStepId);
		if (!sourceStep || sourceStep.transitions.some((t) => t.targetStepId === targetStepId)) return;

		workingService = {
			...workingService,
			steps: workingService.steps.map((step) =>
				step.id === sourceStepId ? { ...step, transitions: [...step.transitions, { targetStepId }] } : step
			)
		};
	}

	/**
	 * Applies a delete gesture from the canvas, Delete on a selection of nodes, edges, or both. Clears
	 * every named route first, then removes every step named outright, patching dangling references to it
	 * the same way handleRemoveStep does, before cascading removeUnreachableSteps across whatever either
	 * change could have orphaned. Deleting the graph's own entry edge on its own is not offered, since a
	 * journey with no entry point at all has nowhere to route from until a different step is made the start.
	 */
	function handleDeleteGraphElements(deleted: {
		stepIds: string[];
		edges: Array<{ sourceStepId: string; targetStepId: string }>;
	}) {
		let next = workingService;

		for (const { sourceStepId, targetStepId } of deleted.edges) {
			next = {
				...next,
				steps: next.steps.map((step) =>
					step.id === sourceStepId
						? { ...step, transitions: step.transitions.filter((t) => t.targetStepId !== targetStepId) }
						: step
				)
			};
			// Deleting the line itself is just as deliberate a decision as the dedicated End action, once it
			// leaves the step with nowhere else to go.
			const source = next.steps.find((step) => step.id === sourceStepId);
			if (source && source.transitions.length === 0) markExplicitEnd(sourceStepId);
		}

		if (deleted.stepIds.length > 0) {
			const removedIds = new Set(deleted.stepIds);
			const steps = next.steps
				.filter((step) => !removedIds.has(step.id))
				.map((step) => ({ ...step, transitions: step.transitions.filter((t) => !removedIds.has(t.targetStepId)) }));
			const startStepId = removedIds.has(next.startStepId) ? (steps[0]?.id ?? next.startStepId) : next.startStepId;
			next = { ...next, startStepId, steps };
		}

		next = removeUnreachableSteps(
			next,
			deleted.edges.map((edge) => edge.targetStepId)
		);

		workingService = next;

		const remainingIds = new Set(workingService.steps.map((step) => step.id));
		if (selectedStepId && !remainingIds.has(selectedStepId)) selectedStepId = null;
		if (editingStepId && !remainingIds.has(editingStepId)) editingStepId = null;
	}

	function handleSetStart(stepId: string) {
		workingService = { ...workingService, startStepId: stepId };
	}

	/**
	 * Clears every route out of a step, then cascades removeUnreachableSteps across whatever those routes
	 * used to lead to, the same "End the journey here" action the graph's own End tool used to offer.
	 */
	function handleEndJourney(stepId: string) {
		const step = workingService.steps.find((candidate) => candidate.id === stepId);
		const oldTargets = step?.transitions.map((transition) => transition.targetStepId) ?? [];

		const cleared = {
			...workingService,
			steps: workingService.steps.map((candidate) =>
				candidate.id === stepId ? { ...candidate, transitions: [] } : candidate
			)
		};
		workingService = removeUnreachableSteps(cleared, oldTargets);
		markExplicitEnd(stepId);

		const remainingIds = new Set(workingService.steps.map((candidate) => candidate.id));
		if (selectedStepId && !remainingIds.has(selectedStepId)) selectedStepId = null;
		if (editingStepId && !remainingIds.has(editingStepId)) editingStepId = null;
	}

	/**
	 * Gives a step its exact set of new onward routes at once, turning it into a branch if it was not
	 * already one, once a draft condition dropped from the toolbar has a real step feeding into it and at
	 * least two real steps it leads to. A target already among the step's routes is left alone rather than
	 * duplicated.
	 */
	function handleAddBranchRoutes(sourceStepId: string, targetStepIds: string[]) {
		const step = workingService.steps.find((candidate) => candidate.id === sourceStepId);
		if (!step) return;
		const existingTargets = new Set(step.transitions.map((t) => t.targetStepId));
		const newRoutes = targetStepIds.filter((id) => !existingTargets.has(id)).map((targetStepId) => ({ targetStepId }));
		if (newRoutes.length === 0) return;

		workingService = {
			...workingService,
			steps: workingService.steps.map((candidate) =>
				candidate.id === sourceStepId
					? { ...candidate, transitions: [...candidate.transitions, ...newRoutes] }
					: candidate
			)
		};
		handleEdit(sourceStepId);
	}
</script>

<svelte:head>
	<title>Edit and review the journey | Service Studio</title>
</svelte:head>

<!-- The stage sequence sits inside this same banner row, as a snippet passed into ServiceHeader, rather
	than as a second row beneath it: this screen's own design keeps the two together, every other route
	keeps them as ServiceHeader followed by a standalone Progress. -->
<ServiceHeader>
	<Progress {stages} compact />
</ServiceHeader>

<main class="editor-page">
	<!-- Spans the full width above the tool rail, canvas and panel, matching the design: this bar is a
		sibling of that whole row, not scoped to the canvas column beneath it. -->
	<div class="editor-page__toolbar">
		<div class="editor-page__toolbar-summary">
			<h2 class="govuk-heading-s govuk-!-margin-bottom-0 editor-page__toolbar-title">{workingService.name}</h2>
			<!-- The same light grey stat boxes as the picker page's step and branch counts, just sized to fit
				this row rather than repeating its large stacked-number treatment. -->
			<div class="editor-page__toolbar-stats">
				<span class="govuk-body-s govuk-!-margin-bottom-0 editor-page__stat">
					<strong>{workingService.steps.length}</strong>
					{workingService.steps.length === 1 ? 'step' : 'steps'}
				</span>
				<span class="govuk-body-s govuk-!-margin-bottom-0 editor-page__stat">
					<strong>{branchCount}</strong>
					{branchCount === 1 ? 'branch' : 'branches'}
				</span>
			</div>
		</div>

		<div class="editor-page__toolbar-controls">
			<label class="govuk-body-s govuk-!-margin-bottom-0 editor-page__branching-toggle">
				<input type="checkbox" bind:checked={showBranching} />
				Show branching
			</label>
		</div>
	</div>

	<div class="editor-page__body">
		<GraphToolbar />

		<div class="editor-page__canvas">
			<JourneyGraph
				bind:this={journeyGraph}
				service={workingService}
				{explicitEndStepIds}
				bind:selectedStepId
				bind:showBranching
				onNodeActivate={handleEdit}
				onConnectSteps={handleConnectSteps}
				onCreateConnectedStep={handleCreateConnectedStep}
				onCreateStep={handleCreateStep}
				onAddBranchRoutes={handleAddBranchRoutes}
				onSetStepEnd={handleEndJourney}
				onDeleteElements={handleDeleteGraphElements}
			/>
		</div>

		<aside class="editor-page__panel">
			{#if editingStepId}
				{@const step = stepsWithNumbers.find((candidate) => candidate.id === editingStepId)}
				{#if step}
					<StepEditorCard
						{step}
						number={step.number}
						otherSteps={stepsWithNumbers
							.filter((other) => other.id !== step.id)
							.map((other) => ({ id: other.id, number: other.number, name: other.name }))}
						canMoveUp={step.number > 1}
						canMoveDown={step.number < stepsWithNumbers.length}
						isStartStep={step.id === workingService.startStepId}
						contextItems={stepContext[step.id] ?? []}
						onContextChange={(items) => handleContextChange(step.id, items)}
						onApply={handleApplyStep}
						onCancel={handleCancelEdit}
						onRemove={handleRemoveStep}
						onMoveUp={(stepId) => handleEditAdjacentStep(stepId, 'up')}
						onMoveDown={(stepId) => handleEditAdjacentStep(stepId, 'down')}
						onSetStart={handleSetStart}
						onEndJourney={handleEndJourney}
					/>
				{/if}
			{:else}
				<div class="editor-page__list">
					<div class="editor-page__list-header">
						<h2 class="govuk-heading-s govuk-!-margin-bottom-0">Steps</h2>
						<p class="govuk-body-s govuk-!-margin-bottom-0 editor-page__list-hint">
							{workingService.steps.length} steps · nothing selected
						</p>
					</div>

					{#each stepsWithNumbers as step, index (step.id)}
						<StepCard
							stepId={step.id}
							number={step.number}
							title={step.name}
							description={step.description}
							tagLabel={humanKind(step.type.kind)}
							tagColour={kindColour(step.type.kind)}
							selected={step.id === selectedStepId}
							canMoveUp={index > 0}
							canMoveDown={index < stepsWithNumbers.length - 1}
							onSelect={handleSelect}
							onEdit={handleEdit}
							onRemove={handleRemoveStep}
							onMoveUp={(stepId) => handleMoveStep(stepId, 'up')}
							onMoveDown={(stepId) => handleMoveStep(stepId, 'down')}
						/>
					{/each}
				</div>

				<div class="editor-page__panel-footer">
					<button class="govuk-button govuk-!-margin-bottom-0" type="button">Send to policy review</button>
				</div>
			{/if}
		</aside>
	</div>
</main>

<style>
	.editor-page {
		display: flex;
		flex-direction: column;
		height: calc(100vh - 74px);
		font-family: 'GDS Transport', arial, sans-serif;
	}

	/* Padding matches .service-header's own 40px so this row's title lines up under GOV.UK, and its
		controls line up under the Experimental prototype flag, rather than each row using its own inset. */
	.editor-page__toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 20px;
		padding: 12px 40px;
		border-bottom: 1px solid #b1b4b6;
	}

	.editor-page__toolbar-summary {
		display: flex;
		align-items: center;
		gap: 12px;
		min-width: 0;
	}

	.editor-page__toolbar-title {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.editor-page__toolbar-stats {
		flex-shrink: 0;
		display: flex;
		border: 1px solid #b1b4b6;
	}

	.editor-page__stat {
		padding: 6px 14px;
		background-color: #f3f2f1;
	}

	.editor-page__stat + .editor-page__stat {
		border-left: 1px solid #b1b4b6;
	}

	.editor-page__toolbar-controls {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		flex-wrap: wrap;
		gap: 15px;
	}

	.editor-page__branching-toggle {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.editor-page__branching-toggle input {
		width: 16px;
		height: 16px;
		accent-color: #0b0c0c;
	}

	.editor-page__body {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	.editor-page__canvas {
		position: relative;
		flex: 1 1 auto;
		min-width: 0;
	}

	.editor-page__panel {
		display: flex;
		flex-direction: column;
		flex: 0 0 400px;
		/* Without this, a flex item's automatic minimum size lets its content, such as a select showing a
			long option, force the panel wider than its flex-basis instead of scrolling within it. */
		min-width: 0;
		min-height: 0;
		background-color: #ffffff;
		border-left: 1px solid #b1b4b6;
	}

	.editor-page__list {
		flex: 1 1 auto;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
	}

	.editor-page__list-header {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 18px 16px 14px;
		border-bottom: 1px solid #b1b4b6;
	}

	.editor-page__list-hint {
		color: #505a5f;
	}

	.editor-page__panel-footer {
		padding: 16px;
	}

	/* GOV.UK's own button is full width only below its tablet breakpoint, auto width above it. This
		panel is much narrower than that breakpoint even on a wide screen, so the button is told to stay
		full width of it regardless of the page's own viewport size. */
	.editor-page__panel-footer .govuk-button {
		width: 100%;
	}

	@media (max-width: 900px) {
		.editor-page__body {
			flex-direction: column;
		}

		.editor-page__panel {
			flex-basis: auto;
			border-left: 0;
			border-top: 1px solid #b1b4b6;
		}
	}
</style>
