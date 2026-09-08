<script lang="ts">
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import Progress from '$lib/components/Progress.svelte';
	import StepCard from '$lib/components/StepCard.svelte';
	import StepEditorCard from '$lib/components/StepEditorCard.svelte';
	import JourneyGraph from '$lib/components/JourneyGraph.svelte';
	import SaveBar from '$lib/components/SaveBar.svelte';
	import { initialSteps } from '$lib/journey/steps';
	import type { JourneyStep } from '$lib/journey/types';

	const stages = [
		{ number: 1, label: 'Start', state: 'complete' as const },
		{ number: 2, label: 'Create', state: 'complete' as const },
		{ number: 3, label: 'Edit and review', state: 'current' as const },
		{ number: 4, label: 'Policy check', state: 'upcoming' as const },
		{ number: 5, label: 'Publish', state: 'upcoming' as const }
	];

	// Raw state because every change below replaces the whole array rather than mutating individual
	// steps in place, matching the pattern already used for the graph's own nodes and edges.
	let steps = $state.raw<JourneyStep[]>(initialSteps);
	// Step 1 starts open so the editing pattern is visible without needing a click first.
	let selectedStepId = $state<string | null>('step-1');

	// The single place a step number is worked out, from its position in the list, so it can never go out
	// of step after an add, remove or reorder.
	let stepsWithNumbers = $derived(steps.map((step, index) => ({ ...step, number: index + 1 })));

	function handleEdit(stepId: string) {
		selectedStepId = stepId;
	}

	function handleApplyStep(updatedStep: JourneyStep) {
		steps = steps.map((step) => (step.id === updatedStep.id ? updatedStep : step));
	}

	/**
	 * Removes a step from the journey once its removal has been confirmed by the card itself, and clears
	 * the open editor if the removed step was the one being edited.
	 */
	function handleRemoveStep(stepId: string) {
		steps = steps.filter((step) => step.id !== stepId);
		if (selectedStepId === stepId) {
			selectedStepId = null;
		}
	}

	/**
	 * Adds a new step at the end of the journey with placeholder content and opens it for editing straight
	 * away, so adding a step immediately exercises the same editing path as any other step.
	 */
	function handleAddStep() {
		const newStep: JourneyStep = {
			id: crypto.randomUUID(),
			title: 'New step',
			description: 'Not yet configured',
			tagLabel: 'Draft',
			tagColour: 'grey',
			answerType: 'question-group',
			branchesTo: null
		};
		steps = [...steps, newStep];
		selectedStepId = newStep.id;
	}

	/**
	 * Swaps a step with its neighbour in the given direction, reordering the shared step list so both the
	 * list and the graph pick up the new sequence. Does nothing if the step is already at that end.
	 */
	function handleMoveStep(stepId: string, direction: 'up' | 'down') {
		const index = steps.findIndex((step) => step.id === stepId);
		if (index === -1) return;

		const targetIndex = direction === 'up' ? index - 1 : index + 1;
		if (targetIndex < 0 || targetIndex >= steps.length) return;

		const reordered = [...steps];
		[reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
		steps = reordered;
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
		<p class="govuk-caption-l">Change driving licence address</p>
		<h1 class="govuk-heading-xl journey-page__title">Edit and review the journey</h1>
		<p class="govuk-body">Reorder, edit and review steps, questions and branching.</p>
	</div>

	<!-- The step list and graph stay together so both views of the same journey can be compared. -->
	<div class="journey-page__columns">
		<section class="journey-page__steps">
			<div class="journey-page__steps-header">
				<h2 class="govuk-heading-m journey-page__steps-heading">Steps</h2>
				<p class="journey-page__steps-hint">{steps.length} steps, use the arrows to reorder</p>
			</div>

			{#each stepsWithNumbers as step, index (step.id)}
				<!-- Whichever step is selected is the one open for editing, so only one card can be open at a time. -->
				{#if step.id === selectedStepId}
					<StepEditorCard
						{step}
						number={step.number}
						otherSteps={stepsWithNumbers
							.filter((other) => other.id !== step.id)
							.map((other) => ({ id: other.id, number: other.number, title: other.title }))}
						canMoveUp={index > 0}
						canMoveDown={index < stepsWithNumbers.length - 1}
						onApply={handleApplyStep}
						onRemove={handleRemoveStep}
						onMoveUp={(stepId) => handleMoveStep(stepId, 'up')}
						onMoveDown={(stepId) => handleMoveStep(stepId, 'down')}
					/>
				{:else}
					<StepCard
						stepId={step.id}
						number={step.number}
						title={step.title}
						description={step.description}
						tagLabel={step.tagLabel}
						tagColour={step.tagColour}
						canMoveUp={index > 0}
						canMoveDown={index < stepsWithNumbers.length - 1}
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
		<JourneyGraph {steps} bind:selectedStepId />
	</div>
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

		.journey-page__columns {
			padding: 0 15px 20px;
		}
	}
</style>
