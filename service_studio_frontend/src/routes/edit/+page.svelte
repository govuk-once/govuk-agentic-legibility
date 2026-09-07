<script lang="ts">
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import Progress from '$lib/components/Progress.svelte';
	import StepCard from '$lib/components/StepCard.svelte';
	import StepEditorCard from '$lib/components/StepEditorCard.svelte';
	import JourneyGraph from '$lib/components/JourneyGraph.svelte';
	import SaveBar from '$lib/components/SaveBar.svelte';

	const stages = [
		{ number: 1, label: 'Load source', state: 'complete' as const },
		{ number: 2, label: 'Edit and review the journey', state: 'current' as const },
		{ number: 3, label: 'Policy checks', state: 'upcoming' as const },
		{ number: 4, label: 'Publish', state: 'upcoming' as const }
	];

	const steps = [
		{
			id: 'step-1',
			number: 1,
			title: 'Sign in with GOV.UK One Login',
			description: 'Authentication · pre-filled from source',
			tagLabel: 'Identity',
			tagColour: 'blue',
			editing: false
		},
		{
			id: 'step-2',
			number: 2,
			title: 'Confirm your identity',
			description: 'Checked against your DVLA record',
			tagLabel: 'Identity',
			tagColour: 'blue',
			editing: false
		},
		{
			id: 'step-3',
			number: 3,
			title: 'Enter your licence details',
			description: '8 questions · 4 pre-filled from source',
			tagLabel: 'Editing',
			tagColour: 'yellow',
			editing: true
		},
		{
			id: 'step-4',
			number: 4,
			title: 'Upload evidence photo',
			description: 'File upload · conditional on branch',
			tagLabel: 'Evidence',
			tagColour: 'purple',
			editing: false
		},
		{
			id: 'step-5',
			number: 5,
			title: 'Check your answers',
			description: 'Summary · generated automatically',
			tagLabel: 'Review',
			tagColour: 'grey',
			editing: false
		},
		{
			id: 'step-6',
			number: 6,
			title: 'Submit and confirm',
			description: 'Declaration · sends to case system',
			tagLabel: 'Submit',
			tagColour: 'green',
			editing: false
		}
	];

	// Shared selection state keeps the graph and step list highlight aligned without coupling their components.
	let selectedStepId = $state<string | null>('step-3');
</script>

<!-- The service header identifies the prototype separately from the editable journey content. -->
<ServiceHeader />

<main class="journey-page">
	<Progress {stages} />

	<!-- Introductory content explains the task before users reach the editing controls. -->
	<div class="journey-page__heading">
		<p class="govuk-caption-l">Renew your driving licence. Schema generated from govuk-forms.json</p>
		<h1 class="govuk-heading-xl journey-page__title">Edit and review the journey</h1>
		<p class="govuk-body">
			Reorder steps, edit questions and review branching. This is the review stage, what you see
			here is what goes to policy.
		</p>
	</div>

	<!-- The step list and graph stay together so both views of the same journey can be compared. -->
	<div class="journey-page__columns">
		<section class="journey-page__steps">
			<div class="journey-page__steps-header">
				<h2 class="govuk-heading-m journey-page__steps-heading">Steps</h2>
				<p class="journey-page__steps-hint">{steps.length} steps · drag to reorder</p>
			</div>

			{#each steps as step (step.id)}
				<!-- Editing steps show their form in place so the list order and graph relationship remain stable. -->
				{#if step.editing}
					<StepEditorCard
						number={step.number}
						title={step.title}
						description={step.description}
						selected={selectedStepId === step.id}
					/>
				{:else}
					<StepCard
						number={step.number}
						title={step.title}
						description={step.description}
						tagLabel={step.tagLabel}
						tagColour={step.tagColour}
						selected={selectedStepId === step.id}
					/>
				{/if}
			{/each}

			<!-- The add control remains after the ordered steps so its insertion point is unambiguous. -->
			<button class="journey-page__add-step" type="button">
				<svg width="14" height="14" viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
					<path d="M7 1 V13 M1 7 H13" fill="none" stroke="#1d70b8" stroke-width="2" />
				</svg>
				Add a step
			</button>
		</section>

		<!-- Graph selection reports a stable step identifier so the matching card can be highlighted. -->
		<JourneyGraph onStepSelect={(stepId) => (selectedStepId = stepId)} />
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
