<script lang="ts">
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import Progress from '$lib/components/Progress.svelte';
	import StepCard from '$lib/components/StepCard.svelte';
	import StepEditorCard from '$lib/components/StepEditorCard.svelte';
	import JourneyGraph from '$lib/graph/JourneyGraph.svelte';
	import SaveBar from '$lib/components/SaveBar.svelte';
	import { serviceExamples } from '$lib/examples';
	import { humanKind, kindColour } from '$lib/schema';
	import type { Service, ServiceStep } from '$lib/schema';

	const stages = [
		{ number: 1, label: 'Start', state: 'complete' as const },
		{ number: 2, label: 'Create', state: 'complete' as const },
		{ number: 3, label: 'Edit and review', state: 'current' as const },
		{ number: 4, label: 'Policy check', state: 'upcoming' as const },
		{ number: 5, label: 'Publish', state: 'upcoming' as const }
	];

	// Which example service is loaded. The examples are bundled and validated at build time, so this is
	// just a slug into that list.
	let selectedSlug = $state(serviceExamples[0]?.slug ?? '');
	const selectedExample = $derived(serviceExamples.find((example) => example.slug === selectedSlug) ?? null);

	// The editable copy of the chosen service. Raw state because every change below replaces the whole
	// object rather than mutating it in place. Seeded from the first example, then reseeded by the effect
	// whenever a different example is chosen, so edits to one example never leak into another.
	let workingService = $state.raw<Service | null>(
		serviceExamples[0]?.service ? structuredClone(serviceExamples[0].service) : null
	);

	// Highlighting only, shared both ways with the graph.
	let selectedStepId = $state<string | null>(null);
	// Which step, if any, is open for editing. Kept separate from selectedStepId so selecting a step,
	// whether from the list or the graph, only ever highlights it rather than forcing its editor open.
	let editingStepId = $state<string | null>(null);

	/**
	 * Reseeds the working copy from the newly chosen example and drops any open editor and selection so
	 * the new graph starts clean. Driven from the dropdown's change event rather than an effect, since a
	 * change of example is a user action, not derived state.
	 */
	function handleExampleChange() {
		workingService = selectedExample?.service ? structuredClone(selectedExample.service) : null;
		editingStepId = null;
		selectedStepId = null;
	}

	// The single place a step number is worked out, from its position in the list, so it can never go out
	// of step after an add, remove or reorder.
	const stepsWithNumbers = $derived(
		(workingService?.steps ?? []).map((step, index) => ({ ...step, number: index + 1 }))
	);

	// Closes whichever editor is open as soon as a different step becomes highlighted, covering every way
	// selectedStepId can change, a list click, a graph click, or clicking Edit elsewhere, in one place
	// rather than repeating the check in each handler. This never fires for the step actually being
	// edited, because handleEdit and handleAddStep always set both ids together.
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
		if (!workingService) return;
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
		if (!workingService) return;

		const steps = workingService.steps
			.filter((step) => step.id !== stepId)
			.map((step) => ({
				...step,
				transitions: step.transitions.filter((transition) => transition.targetStepId !== stepId)
			}));
		const startStepId =
			workingService.startStepId === stepId
				? (steps[0]?.id ?? workingService.startStepId)
				: workingService.startStepId;

		workingService = { ...workingService, startStepId, steps };
		if (selectedStepId === stepId) selectedStepId = null;
		if (editingStepId === stepId) editingStepId = null;
	}

	/**
	 * Adds a new information step at the end of the service with placeholder content and opens it for
	 * editing straight away, so adding a step immediately exercises the same editing path as any other.
	 */
	function handleAddStep() {
		if (!workingService) return;

		const newStep: ServiceStep = {
			id: crypto.randomUUID(),
			type: { kind: 'info', body: '' },
			name: 'New step',
			description: 'Not yet configured',
			fields: [],
			transitions: []
		};
		workingService = { ...workingService, steps: [...workingService.steps, newStep] };
		editingStepId = newStep.id;
		selectedStepId = newStep.id;
	}

	/**
	 * Swaps a step with its neighbour in the given direction, reordering the service step list so both
	 * the list and the graph pick up the new sequence. Order is presentational only: ids drive the
	 * transitions and the layout, so a swap cannot break the routing.
	 */
	function handleMoveStep(stepId: string, direction: 'up' | 'down') {
		if (!workingService) return;

		const index = workingService.steps.findIndex((step) => step.id === stepId);
		if (index === -1) return;

		const targetIndex = direction === 'up' ? index - 1 : index + 1;
		if (targetIndex < 0 || targetIndex >= workingService.steps.length) return;

		const reordered = [...workingService.steps];
		[reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
		workingService = { ...workingService, steps: reordered };
	}
</script>

<svelte:head>
	<title>Edit and review the journey | Service Studio</title>
</svelte:head>

<!-- The service header identifies the prototype separately from the editable journey content. -->
<ServiceHeader />

<main class="journey-page">
	<Progress {stages} />

	<!-- Introductory content explains the task before users reach the editing controls. -->
	<div class="journey-page__heading">
		<p class="govuk-caption-l">{selectedExample?.service?.name ?? 'Journey editor'}</p>
		<h1 class="govuk-heading-xl journey-page__title">Edit and review the journey</h1>
		<p class="govuk-body">Reorder, edit and review steps, questions and branching.</p>

		<!-- Choosing an example loads a validated canonical schema from src/lib/examples. -->
		<div class="govuk-form-group journey-page__example">
			<label class="govuk-label govuk-label--s" for="example-service">Example service</label>
			<select
				class="govuk-select"
				id="example-service"
				bind:value={selectedSlug}
				onchange={handleExampleChange}
			>
				{#each serviceExamples as example (example.slug)}
					<option value={example.slug}>{example.name}</option>
				{/each}
			</select>
		</div>
	</div>

	{#if selectedExample && !selectedExample.service}
		<!-- The chosen file did not match the canonical schema, so its issues are shown instead of a graph. -->
		<div class="journey-page__error">
			<div class="govuk-error-summary" role="alert">
				<h2 class="govuk-error-summary__title">This example does not match the canonical schema</h2>
				<div class="govuk-error-summary__body">
					<ul class="govuk-list govuk-error-summary__list">
						{#each selectedExample.issues as issue, index (index)}
							<li>{issue.path}: {issue.message}</li>
						{/each}
					</ul>
				</div>
			</div>
		</div>
	{:else if workingService}
		<!-- The step list and graph stay together so both views of the same journey can be compared. -->
		<div class="journey-page__columns">
			<section class="journey-page__steps">
				<div class="journey-page__steps-header">
					<h2 class="govuk-heading-m journey-page__steps-heading">Steps</h2>
					<p class="journey-page__steps-hint">
						{workingService.steps.length} steps, use the arrows to reorder
					</p>
				</div>

				{#each stepsWithNumbers as step, index (step.id)}
					<!-- Editing is its own state, separate from highlighting, so only an explicit Edit click opens a step. -->
					{#if step.id === editingStepId}
						<StepEditorCard
							{step}
							number={step.number}
							otherSteps={stepsWithNumbers
								.filter((other) => other.id !== step.id)
								.map((other) => ({ id: other.id, number: other.number, name: other.name }))}
							canMoveUp={index > 0}
							canMoveDown={index < stepsWithNumbers.length - 1}
							onApply={handleApplyStep}
							onCancel={handleCancelEdit}
							onRemove={handleRemoveStep}
							onMoveUp={(stepId) => handleMoveStep(stepId, 'up')}
							onMoveDown={(stepId) => handleMoveStep(stepId, 'down')}
						/>
					{:else}
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
					{/if}
				{/each}

				<!-- The add control remains after the ordered steps so its insertion point is unambiguous. -->
				<button class="journey-page__add-step" type="button" onclick={handleAddStep}>
					<svg width="14" height="14" viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
						<path d="M7 1 V13 M1 7 H13" fill="none" stroke="#1d70b8" stroke-width="2" />
					</svg>
					Add a step
				</button>
			</section>

			<!-- Selection is shared both ways so a graph click and an Edit click in the list stay in sync. -->
			<JourneyGraph service={workingService} bind:selectedStepId />
		</div>
	{/if}
</main>

<!-- Save actions remain outside the main editor so they can form a consistent page footer. -->
<SaveBar />

<style>
	.journey-page {
		flex-grow: 1;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.journey-page__heading {
		padding: 30px 40px 25px;
	}

	.journey-page__heading .govuk-caption-l {
		margin-bottom: 10px;
	}

	.journey-page__title {
		margin-bottom: 10px;
	}

	.journey-page__example {
		margin-top: 20px;
		margin-bottom: 0;
	}

	.journey-page__example .govuk-select {
		max-width: 420px;
	}

	.journey-page__error {
		padding: 0 40px 30px;
	}

	.journey-page__columns {
		display: flex;
		align-items: flex-start;
		gap: 30px;
		padding: 0 40px 30px;
	}

	.journey-page__steps {
		display: flex;
		flex-direction: column;
		flex-shrink: 0;
		gap: 10px;
		width: 620px;
	}

	.journey-page__steps-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.journey-page__steps-heading {
		margin-bottom: 0;
	}

	.journey-page__steps-hint {
		margin: 0;
		font-size: 1rem;
		color: #505a5f;
	}

	.journey-page__add-step {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		padding: 15px;
		background-color: transparent;
		border: 1px dashed #505a5f;
		font-family: inherit;
		font-size: 1.0625rem;
		font-weight: 700;
		color: #1d70b8;
		cursor: pointer;
	}

	@media (max-width: 1100px) {
		.journey-page__columns {
			flex-direction: column;
		}

		.journey-page__steps {
			width: 100%;
		}
	}

	@media (max-width: 640px) {
		.journey-page__heading {
			padding: 20px 15px;
		}

		.journey-page__columns,
		.journey-page__error {
			padding: 0 15px 20px;
		}
	}
</style>
