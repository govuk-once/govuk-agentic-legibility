<script lang="ts">
	import { untrack } from 'svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import Progress from '$lib/components/Progress.svelte';
	import StepCard from '$lib/components/StepCard.svelte';
	import StepEditorCard from '$lib/components/StepEditorCard.svelte';
	import JourneyGraph from '$lib/graph/JourneyGraph.svelte';
	import GraphToolbar from '$lib/graph/GraphToolbar.svelte';
	import { humanKind, isBranchStep, kindColour } from '$lib/schema';
	import type { Service, ServiceStep, StepTransition } from '$lib/schema';
	import type { ArmedTool } from '$lib/graph/types';
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

	// Tracks which step is highlighted. Shared both ways with the graph, so selecting a step in the list
	// also highlights it on the canvas, and the other way round.
	let selectedStepId = $state<string | null>(null);
	// Which step, if any, is open for editing. Kept separate from selectedStepId so selecting a step,
	// whether from the list or the graph, only ever highlights it rather than forcing its editor open.
	let editingStepId = $state<string | null>(null);
	// Which toolbar tool, if any, is armed. Set from the toolbar, read and cleared by handleNodeActivate.
	let armedTool = $state<ArmedTool>(null);
	// Owned here, rather than inside JourneyGraph, because the design's own toolbar controlling them sits
	// above the whole editor body, not scoped to the canvas column alone.
	let showBranching = $state(true);
	let zoom = $state(1);
	// The graph component instance, so the page's toolbar buttons can trigger its fit and zoom step
	// behaviour without duplicating the pan and zoom maths that already lives there.
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
		editingStepId = null;
		selectedStepId = null;
		armedTool = null;
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
	 * Inserts a new step onto one specific route leading out of stepId: the route that currently leads to
	 * targetStepId, or, when targetStepId is null, the step's own dead end. Working out which route by
	 * its target, rather than assuming a step only ever has one, is what makes this work for a branch
	 * step's routes too. The new step takes over that one route's old target, and if that route had a
	 * label or a condition, the new step keeps it, so the branch still means what it did before. The
	 * step's other routes, if it has any, are left alone. The made up id 'start' is handled separately
	 * below, since inserting there puts a new step before the very first step rather than after an
	 * existing one.
	 */
	function handleInsertAfter(stepId: string, targetStepId: string | null) {
		if (stepId === 'start') {
			handleInsertAtStart();
			return;
		}

		const sourceIndex = workingService.steps.findIndex((step) => step.id === stepId);
		const sourceStep = workingService.steps[sourceIndex];
		if (!sourceStep) return;

		const newStep: ServiceStep = {
			id: crypto.randomUUID(),
			type: { kind: 'info', body: '' },
			name: 'New step',
			description: 'Not yet configured',
			fields: [],
			transitions: []
		};

		let nextTransitions: StepTransition[];
		if (targetStepId === null) {
			// Inserting after the step's own dead end: only valid while it still has none, so a stale "+"
			// left over from before this step gained a route cannot silently add a second one.
			if (sourceStep.transitions.length !== 0) return;
			nextTransitions = [{ targetStepId: newStep.id }];
		} else {
			const transitionIndex = sourceStep.transitions.findIndex((t) => t.targetStepId === targetStepId);
			if (transitionIndex === -1) return; // that route no longer exists either: also out of date, stop here
			newStep.transitions = [{ targetStepId }];
			// Changing just this one route, rather than rebuilding the whole list, is what keeps its label
			// and condition, if it had any, attached to it now that it leads to the new step first.
			nextTransitions = sourceStep.transitions.map((transition, index) =>
				index === transitionIndex ? { ...transition, targetStepId: newStep.id } : transition
			);
		}

		const steps = [...workingService.steps];
		steps[sourceIndex] = { ...sourceStep, transitions: nextTransitions };
		steps.splice(sourceIndex + 1, 0, newStep);

		workingService = { ...workingService, steps };
		editingStepId = newStep.id;
		selectedStepId = newStep.id;
	}

	/**
	 * Inserts a new step before the current entry point: the new step becomes the journey's start and
	 * takes over the old entry step as its own single route, mirroring what handleInsertAfter does for
	 * every other single-route step, just with the graph's own start terminal standing in for a source.
	 */
	function handleInsertAtStart() {
		const newStep: ServiceStep = {
			id: crypto.randomUUID(),
			type: { kind: 'info', body: '' },
			name: 'New step',
			description: 'Not yet configured',
			fields: [],
			transitions: [{ targetStepId: workingService.startStepId }]
		};

		workingService = {
			...workingService,
			startStepId: newStep.id,
			steps: [newStep, ...workingService.steps]
		};
		editingStepId = newStep.id;
		selectedStepId = newStep.id;
	}

	/**
	 * Reports a step node click on the graph. With no tool armed this opens the step for editing directly,
	 * since clicking a step on the canvas is the primary way into its editor. With a tool armed it applies
	 * that tool to the clicked step instead, then disarms, since click to arm then click a target is a one
	 * shot action.
	 */
	function handleNodeActivate(stepId: string) {
		const tool = armedTool;
		armedTool = null;

		if (!tool) {
			handleEdit(stepId);
			return;
		}

		if (tool === 'step') {
			// Clicking the step itself, rather than one of its own route "+" buttons, only makes sense
			// while it is clear which route to insert into: no route yet, or exactly one. A branch step
			// has more than one, so this does nothing there, its own routes each have a "+" for this instead.
			const clickedStep = workingService.steps.find((step) => step.id === stepId);
			if (!clickedStep || clickedStep.transitions.length > 1) return;
			handleInsertAfter(stepId, clickedStep.transitions[0]?.targetStepId ?? null);
			return;
		}

		if (tool === 'start') {
			workingService = { ...workingService, startStepId: stepId };
			return;
		}

		if (tool === 'end') {
			const clickedStep = workingService.steps.find((step) => step.id === stepId);
			const oldTargets = clickedStep?.transitions.map((transition) => transition.targetStepId) ?? [];

			const cleared = {
				...workingService,
				steps: workingService.steps.map((step) => (step.id === stepId ? { ...step, transitions: [] } : step))
			};
			workingService = removeUnreachableSteps(cleared, oldTargets);

			// A step this cleared away, rather than just its own route, could be the one currently
			// selected or open for editing, if it was chosen before this action removed it.
			const remainingIds = new Set(workingService.steps.map((step) => step.id));
			if (selectedStepId && !remainingIds.has(selectedStepId)) selectedStepId = null;
			if (editingStepId && !remainingIds.has(editingStepId)) editingStepId = null;
			return;
		}

		// tool === 'condition': the clicked step must end up with at least two routes to actually be a
		// branch, not one, so a dead end (no routes yet) gets two new targets rather than just one, which
		// would otherwise leave it as a plain continuation instead of a branch.
		const clickedStep = workingService.steps.find((step) => step.id === stepId);
		if (!clickedStep) return;
		const candidates = workingService.steps.filter((step) => step.id !== stepId);
		const routesNeeded = Math.max(1, 2 - clickedStep.transitions.length);
		const newRoutes = candidates.slice(0, routesNeeded).map((candidate) => ({ targetStepId: candidate.id }));
		if (newRoutes.length === 0) return;

		workingService = {
			...workingService,
			steps: workingService.steps.map((step) =>
				step.id === stepId ? { ...step, transitions: [...step.transitions, ...newRoutes] } : step
			)
		};
		handleEdit(stepId);
	}

	function handleArmTool(tool: ArmedTool) {
		armedTool = tool;
	}

	const ARMED_TOOL_HINT: Record<Exclude<ArmedTool, null>, string> = {
		step: 'Click a step to insert a new one after it.',
		condition: 'Click a step to add a branch route to it.',
		start: 'Click a step to make it the entry point.',
		end: 'Click a step to clear its onward routes.'
	};
</script>

<svelte:head>
	<title>Edit and review the journey | Service Studio</title>
</svelte:head>

<!-- Cancels an armed tool without needing a dedicated on screen button for it, matching the toolbar's own
	toggle-off as the other way to cancel. -->
<svelte:window
	onkeydown={(event) => {
		if (event.key === 'Escape') armedTool = null;
	}}
/>

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

			<button class="editor-page__fit" type="button" onclick={() => journeyGraph?.fit()}>Fit</button>

			<div class="editor-page__zoom">
				<button type="button" onclick={() => journeyGraph?.zoomOut()} aria-label="Zoom out">−</button>
				<span class="editor-page__zoom-level">{Math.round(zoom * 100)}%</span>
				<button type="button" onclick={() => journeyGraph?.zoomIn()} aria-label="Zoom in">+</button>
			</div>
		</div>
	</div>

	<div class="editor-page__body">
		<GraphToolbar {armedTool} onarm={handleArmTool} />

		<div class="editor-page__canvas" class:editor-page__canvas--armed={armedTool !== null}>
			{#if armedTool}
				<p class="editor-page__armed-hint govuk-body-s govuk-!-margin-bottom-0" role="status">
					{ARMED_TOOL_HINT[armedTool]} Press Escape to cancel.
				</p>
			{/if}
			<JourneyGraph
				bind:this={journeyGraph}
				service={workingService}
				bind:selectedStepId
				bind:showBranching
				bind:zoom
				onNodeActivate={handleNodeActivate}
				onInsertAfter={handleInsertAfter}
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
						onApply={handleApplyStep}
						onCancel={handleCancelEdit}
						onRemove={handleRemoveStep}
						onMoveUp={(stepId) => handleEditAdjacentStep(stepId, 'up')}
						onMoveDown={(stepId) => handleEditAdjacentStep(stepId, 'down')}
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

	/* An overlay on the canvas itself, near the tool rail the armed tool came from, rather than a banner
		near the stage nav at the top of the page: this is feedback about the canvas, so it belongs on it. */
	.editor-page__armed-hint {
		position: absolute;
		top: 15px;
		left: 15px;
		z-index: 1;
		max-width: calc(100% - 30px);
		margin: 0;
		padding: 8px 12px;
		background-color: #ffffff;
		border: 1px solid #1d70b8;
		color: #1d70b8;
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

	/* GOV.UK's own button component has no outline variant, and its secondary button carries a grey fill
		that the design for this screen deliberately avoids, so Fit is a plain bordered button instead. */
	.editor-page__fit {
		padding: 6px 12px;
		background: none;
		border: 1px solid #b1b4b6;
		font-family: inherit;
		font-size: 1rem;
		font-weight: 700;
		color: #0b0c0c;
		cursor: pointer;
	}

	.editor-page__zoom {
		display: flex;
		align-items: center;
		border: 1px solid #b1b4b6;
	}

	.editor-page__zoom button {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		background: none;
		border: 0;
		border-right: 1px solid #b1b4b6;
		font-size: 1rem;
		font-weight: 700;
		cursor: pointer;
	}

	.editor-page__zoom-level {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 46px;
		height: 28px;
		border-right: 1px solid #b1b4b6;
		font-size: 0.875rem;
	}

	.editor-page__zoom button:last-child {
		border-right: 0;
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

	.editor-page__canvas--armed :global(.journey-graph__canvas) {
		cursor: crosshair;
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
