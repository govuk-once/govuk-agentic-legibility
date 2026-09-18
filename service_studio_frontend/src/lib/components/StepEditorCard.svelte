<script lang="ts">
	import RemoveStepConfirm from './RemoveStepConfirm.svelte';
	import StepReorderButtons from './StepReorderButtons.svelte';
	import { defaultStepType } from '$lib/schema';
	import type { ServiceStep, ServiceStepKind, StepTransition } from '$lib/schema';

	interface OtherStep {
		id: string;
		number: number;
		name: string;
	}

	interface Props {
		step: ServiceStep;
		number: number;
		otherSteps: OtherStep[];
		canMoveUp: boolean;
		canMoveDown: boolean;
		onApply: (updatedStep: ServiceStep) => void;
		onCancel: (stepId: string) => void;
		onRemove: (stepId: string) => void;
		onMoveUp: (stepId: string) => void;
		onMoveDown: (stepId: string) => void;
	}

	let {
		step,
		number,
		otherSteps,
		canMoveUp,
		canMoveDown,
		onApply,
		onCancel,
		onRemove,
		onMoveUp,
		onMoveDown
	}: Props = $props();

	// The kinds the delivery-type select offers, in the order they are shown.
	const KIND_OPTIONS: { value: ServiceStepKind; label: string }[] = [
		{ value: 'info', label: 'Information' },
		{ value: 'endpoint', label: 'API endpoint' },
		{ value: 'phone', label: 'Phone' },
		{ value: 'person', label: 'In person' },
		{ value: 'letter', label: 'Letter' }
	];

	// The component identifier keeps label targets unique when more than one step is open for editing.
	const componentId = $props.id();

	const totalSteps = $derived(otherSteps.length + 1);

	// Held locally so typing does not touch the shared service until Apply commits it. Seeded empty
	// rather than from step here, because the effect below populates the real values immediately on
	// mount, and seeding from step directly would leave a stale copy that only matches step by
	// coincidence at declaration time rather than by being kept in sync.
	let draftName = $state('');
	let draftDescription = $state('');
	let draftKind = $state<ServiceStepKind>('info');
	// One target step id per onward transition. An empty first entry means the step ends the journey.
	let draftTargets = $state<string[]>([]);
	// A label per transition, index matched with draftTargets. Only shown and editable for a branching
	// step: a single route is normally the unconditional default path, so there is nothing meaningful to
	// label there. A route's own condition, if it has one, is not edited here and is preserved as is when
	// its target is left unchanged, this panel only names the route.
	let draftLabels = $state<string[]>([]);

	// Confirming locally, rather than removing on the first click, guards against an accidental click on
	// Remove step losing a step's edits.
	let confirmingRemoval = $state(false);

	// A step with more than one onward route is a branch, so its targets are edited one row per route
	// rather than as a single "continues to" choice.
	const isBranch = $derived(draftTargets.length >= 2);

	/**
	 * Sets the drafts back to the step's currently committed values.
	 */
	function resetDraftFromStep() {
		draftName = step.name;
		draftDescription = step.description;
		draftKind = step.type.kind;
		draftTargets = step.transitions.length > 0 ? step.transitions.map((t) => t.targetStepId) : [''];
		draftLabels = step.transitions.length > 0 ? step.transitions.map((t) => t.label ?? '') : [''];
	}

	// Keeps the drafts matching step whenever it changes, which is what makes opening a different step
	// start clean rather than carrying over the previous step's unsaved edits.
	$effect(() => {
		resetDraftFromStep();
	});

	/**
	 * Builds the updated step from the current drafts and commits it to the shared service. Closing the
	 * editor is left to the parent, via onApply, since selection and editing state both live there.
	 * Changing the kind swaps in a minimal valid type object, since the old kind's delivery details no
	 * longer apply. A route's condition is not edited here, so it is carried over untouched when that
	 * route's target is left pointing at the same step, and dropped when the target changes, since a
	 * condition written for the old target would no longer describe the new one.
	 */
	function applyChanges() {
		const nextType = draftKind === step.type.kind ? step.type : defaultStepType(draftKind);

		let nextTransitions: StepTransition[];
		if (draftTargets.length <= 1) {
			const target = draftTargets[0] ?? '';
			if (!target) {
				nextTransitions = [];
			} else {
				const existing = step.transitions.find((t) => t.targetStepId === target);
				nextTransitions = [existing ?? { targetStepId: target }];
			}
		} else {
			nextTransitions = draftTargets.map((target, index) => {
				const existing = step.transitions[index];
				const condition = existing?.targetStepId === target ? existing.condition : undefined;
				return {
					targetStepId: target,
					...(draftLabels[index] ? { label: draftLabels[index] } : {}),
					...(condition ? { condition } : {})
				};
			});
		}

		onApply({
			...step,
			name: draftName,
			description: draftDescription,
			type: nextType,
			transitions: nextTransitions
		});
	}
</script>

<div class="step-editor" role="group" aria-label="Step {number}: {step.name}, editing">
	<!-- The header repeats the step identity so the open form remains tied to its journey position. -->
	<div class="step-editor__header">
		<StepReorderButtons
			label="step {number}: {step.name}"
			groupLabel="Move between steps"
			upLabel="Edit the previous step"
			downLabel="Edit the next step"
			{canMoveUp}
			{canMoveDown}
			onMoveUp={() => onMoveUp(step.id)}
			onMoveDown={() => onMoveDown(step.id)}
		/>
		<span class="govuk-body-s govuk-!-font-weight-bold govuk-!-margin-bottom-0 step-editor__number"
			>{number}</span
		>
		<div class="step-editor__summary">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-0">{step.name}</h3>
			<p class="govuk-body-s govuk-!-margin-bottom-0 step-editor__status">
				Editing · step {number} of {totalSteps}
			</p>
		</div>
	</div>

	<!-- Form controls use unique identifiers so labels remain correct when several editors are rendered. -->
	<div class="step-editor__form">
		<div class="govuk-form-group step-editor__form-group">
			<label class="govuk-label govuk-label--s" for="{componentId}-step-name">Step name</label>
			<input
				class="govuk-input"
				id="{componentId}-step-name"
				name="step-name"
				type="text"
				bind:value={draftName}
			/>
		</div>

		<div class="govuk-form-group step-editor__form-group">
			<label class="govuk-label govuk-label--s" for="{componentId}-step-description">Step description</label>
			<textarea
				class="govuk-textarea govuk-!-margin-bottom-0"
				id="{componentId}-step-description"
				name="step-description"
				rows="2"
				bind:value={draftDescription}
			></textarea>
		</div>

		<div class="govuk-form-group step-editor__form-group">
			<label class="govuk-label govuk-label--s" for="{componentId}-step-type">Step type</label>
			<div id="{componentId}-step-type-hint" class="govuk-hint govuk-!-margin-bottom-1">
				Changing the type replaces the step's delivery details.
			</div>
			<select
				class="govuk-select"
				id="{componentId}-step-type"
				name="step-type"
				aria-describedby="{componentId}-step-type-hint"
				bind:value={draftKind}
			>
				{#each KIND_OPTIONS as option (option.value)}
					<option value={option.value}>{option.label}</option>
				{/each}
			</select>
		</div>

		{#if !isBranch}
			<div class="govuk-form-group step-editor__form-group">
				<label class="govuk-label govuk-label--s" for="{componentId}-continues-to">Continues to</label>
				<select
					class="govuk-select"
					id="{componentId}-continues-to"
					name="continues-to"
					bind:value={draftTargets[0]}
				>
					<option value="">Ends the journey</option>
					{#each otherSteps as other (other.id)}
						<option value={other.id}>Step {other.number}: {other.name}</option>
					{/each}
				</select>
			</div>
		{:else}
			<fieldset class="govuk-fieldset step-editor__form-group">
				<legend class="govuk-fieldset__legend govuk-fieldset__legend--s">Branch routes</legend>
				{#each draftTargets as target, index (index)}
					<div class="step-editor__route">
						<div class="govuk-form-group step-editor__form-group">
							<label class="govuk-label govuk-label--s" for="{componentId}-route-{index}-label">
								Route {index + 1} label
							</label>
							<input
								class="govuk-input"
								id="{componentId}-route-{index}-label"
								type="text"
								bind:value={draftLabels[index]}
							/>
						</div>

						<div class="govuk-form-group step-editor__form-group">
							<label class="govuk-label govuk-label--s" for="{componentId}-route-{index}">
								Route {index + 1} target
							</label>
							<select
								class="govuk-select"
								id="{componentId}-route-{index}"
								name="route-{index}"
								bind:value={draftTargets[index]}
							>
								{#each otherSteps as other (other.id)}
									<option value={other.id}>Step {other.number}: {other.name}</option>
								{/each}
							</select>
						</div>
					</div>
				{/each}
			</fieldset>
		{/if}

		<!-- Fields are shown for reference. A fuller editor for them is still to come. -->
		<p class="govuk-body-s step-editor__fields-note govuk-!-margin-bottom-0">
			Collects {step.fields.length}
			{step.fields.length === 1 ? 'field' : 'fields'}, not editable yet.
		</p>

		{#if confirmingRemoval}
			<RemoveStepConfirm onRemove={() => onRemove(step.id)} onCancel={() => (confirmingRemoval = false)} />
		{:else}
			<div class="step-editor__actions">
				<button class="govuk-button step-editor__apply" type="button" onclick={applyChanges}>
					Apply changes
				</button>
				<button
					type="button"
					class="govuk-link govuk-body-s govuk-!-margin-bottom-0"
					onclick={() => onCancel(step.id)}
				>
					Cancel
				</button>
				<button
					type="button"
					class="govuk-link govuk-body-s govuk-!-margin-bottom-0 step-editor__remove"
					onclick={() => (confirmingRemoval = true)}
				>
					Remove step
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	.step-editor {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-height: 0;
		background-color: #ffffff;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.step-editor__header {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 18px 16px 14px;
		border-bottom: 1px solid #b1b4b6;
	}

	.step-editor__number {
		flex-shrink: 0;
		padding-top: 2px;
		color: #505a5f;
	}

	.step-editor__summary {
		display: flex;
		flex-direction: column;
		gap: 2px;
		/* Without this, a flex item's automatic minimum size lets its content force this column, and the
			panel around it, wider than it should be instead of wrapping within it. */
		min-width: 0;
	}

	.step-editor__status {
		color: #505a5f;
	}

	.step-editor__form {
		flex: 1 1 auto;
		min-width: 0;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 15px;
		padding: 16px;
	}

	.step-editor__form-group {
		min-width: 0;
		margin-bottom: 0;
	}

	/* .govuk-select has no width rule of its own the way .govuk-input does, so left alone it sizes to its
		longest option instead of filling the field the way every other control in this form does. */
	.step-editor__form-group .govuk-select {
		width: 100%;
	}

	.step-editor__route {
		display: flex;
		flex-direction: column;
		gap: 12px;
		min-width: 0;
	}

	.step-editor__route + .step-editor__route {
		margin-top: 15px;
		padding-top: 15px;
		border-top: 1px solid #b1b4b6;
	}

	.step-editor__fields-note {
		color: #505a5f;
	}

	.step-editor__actions {
		display: flex;
		align-items: center;
		gap: 20px;
	}

	.step-editor__apply {
		margin-bottom: 0;
	}

	.step-editor__remove {
		color: #d4351c;
	}

	@media (max-width: 640px) {
		.step-editor__header,
		.step-editor__actions {
			align-items: flex-start;
			flex-wrap: wrap;
		}
	}
</style>
