<script lang="ts">
	import { untrack } from 'svelte';
	import { describeCondition } from '$lib/service-editor/graph/describe-value';
	import {
		convertState,
		convertTargetTypes,
		isConvertTargetType,
		isConvertible,
		lostByConversion
	} from '$lib/service-editor/schema/convert-state';
	import type { TargetOption } from '$lib/service-editor/graph/state-rows';
	import {
		descriptionOf,
		hasNext,
		hasText,
		textOf,
		withChoiceTargets,
		withNext,
		withText,
		withTitleAndDescription
	} from '$lib/schema/workflow/edit-state';
	import type { State } from '$lib/schema/workflow/process';
	import type { WorkflowIssue } from '$lib/schema/workflow/validate';

	interface Props {
		// The state as it is now. The form starts from it and only changes a copy.
		currentState: State;
		// The code of the state, so it is left out of the choices for where it continues to.
		stateCode: string;
		// Every state that a route could lead to, named for a list of choices.
		targets: TargetOption[];
		// Called with the changed state when the person applies. It returns any problems the schema found
		// with the result, and an empty list when the change was accepted.
		onApply: (updated: State) => WorkflowIssue[];
		// Called when the form should close, after a change is applied or when the person cancels.
		onClose: () => void;
	}

	let { currentState, stateCode, targets, onApply, onClose }: Props = $props();

	// Makes the id of each field unique, so the labels stay correct if two forms are ever on the page.
	const fieldId = $props.id();

	// What the person is typing. It is held here, and not in the workflow, until they choose Apply changes.
	// The form is shown afresh for each state, so it only needs the values the state had when it opened.
	// The type chosen in the list. It starts as the current type, so nothing changes unless the person picks
	// another one. It is held as text because it comes from a list of choices.
	let draftType = $state<string>(untrack(() => currentState.type));
	let draftText = $state(untrack(() => textOf(currentState)));
	let draftTitle = $state(untrack(() => currentState.name ?? ''));
	let draftDescription = $state(untrack(() => descriptionOf(currentState)));
	// The state it continues to. A choice or an end has none, so this stays empty for them and is not used.
	let draftNext = $state(untrack(() => (hasNext(currentState) ? currentState.next : '')));
	// Where each rule of a choice leads, in the order of its rules, and where its default leads. A state that
	// is not a choice has none, so these stay empty for it and are not used.
	let draftRuleTargets = $state(untrack(() => (currentState.type === 'choice' ? currentState.rules.map((rule) => rule.next) : [])));
	let draftDefault = $state(untrack(() => (currentState.type === 'choice' ? currentState.default : '')));
	let issues = $state<WorkflowIssue[]>([]);

	// The types offered. Invoke is only listed on a step that already is one, because nothing can be changed
	// into it.
	const typeChoices = $derived<string[]>(currentState.type === 'invoke' ? [...convertTargetTypes, 'invoke'] : [...convertTargetTypes]);

	// What changing to the chosen type would remove, in plain words, shown before the person applies.
	const lost = $derived(
		isConvertible(currentState) && isConvertTargetType(draftType) ? lostByConversion(currentState, draftType) : []
	);

	// A state cannot continue to itself, so it is not offered as a choice.
	const nextChoices = $derived(targets.filter((target) => target.stateId !== stateCode));

	/**
	 * Builds the changed state from the form and hands it over. The form closes only if the change was
	 * accepted, so a problem is shown next to what caused it and nothing typed is lost.
	 */
	function apply() {
		// The type is changed first, and then what was typed in the form is put onto the result. The words are
		// only put back if the form had a field for them and the new type has words to put them in.
		const converted = isConvertTargetType(draftType) ? convertState(currentState, draftType, stateCode) : currentState;
		const withWords = hasText(currentState) && hasText(converted) ? withText(converted, draftText) : converted;
		const changed = withTitleAndDescription(withWords, draftTitle, draftDescription);
		issues = onApply(withChoiceTargets(withNext(changed, draftNext), draftRuleTargets, draftDefault));
		if (issues.length === 0) onClose();
	}
</script>

<form
	class="state-editor"
	onsubmit={(event) => {
		event.preventDefault();
		apply();
	}}
>
	{#if issues.length > 0}
		<div class="govuk-error-summary" role="alert">
			<h2 class="govuk-error-summary__title">This change cannot be applied</h2>
			<div class="govuk-error-summary__body">
				<ul class="govuk-list govuk-error-summary__list">
					{#each issues as issue, index (index)}
						<li>{issue.path}: {issue.message}</li>
					{/each}
				</ul>
			</div>
		</div>
	{/if}

	{#if isConvertible(currentState)}
		<div class="govuk-form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-type">Type</label>
			<div id="{fieldId}-type-hint" class="govuk-hint">
				Changing the type removes the details that belong to the old type.
			</div>
			<select
				class="govuk-select"
				id="{fieldId}-type"
				aria-describedby="{fieldId}-type-hint"
				bind:value={draftType}
			>
				{#each typeChoices as type (type)}
					<option value={type}>{type}</option>
				{/each}
			</select>
		</div>

		{#if lost.length > 0}
			<div class="govuk-warning-text">
				<span class="govuk-warning-text__icon" aria-hidden="true">!</span>
				<strong class="govuk-warning-text__text">
					<span class="govuk-visually-hidden">Warning</span>
					Changing to {draftType} will remove {lost.join(', ')}.
				</strong>
			</div>
		{/if}
	{/if}

	{#if hasText(currentState) && (draftType === 'input' || draftType === 'output')}
		<div class="govuk-form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-text">
				{draftType === 'input' ? 'Question' : 'Message'}
			</label>
			<textarea class="govuk-textarea" id="{fieldId}-text" rows="4" required bind:value={draftText}></textarea>
		</div>
	{/if}

	<div class="govuk-form-group">
		<label class="govuk-label govuk-label--s" for="{fieldId}-title">Title</label>
		<div id="{fieldId}-title-hint" class="govuk-hint">Leave blank to use the wording the step already has.</div>
		<input
			class="govuk-input"
			id="{fieldId}-title"
			type="text"
			aria-describedby="{fieldId}-title-hint"
			bind:value={draftTitle}
		/>
	</div>

	<div class="govuk-form-group">
		<label class="govuk-label govuk-label--s" for="{fieldId}-description">Description</label>
		<textarea class="govuk-textarea" id="{fieldId}-description" rows="3" bind:value={draftDescription}></textarea>
	</div>

	{#if hasNext(currentState)}
		<div class="govuk-form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-next">Continues to</label>
			<select class="govuk-select state-editor__select" id="{fieldId}-next" bind:value={draftNext}>
				{#each nextChoices as target (target.stateId)}
					<option value={target.stateId}>{target.label}</option>
				{/each}
			</select>
		</div>
	{/if}

	{#if currentState.type === 'choice'}
		<!-- The conditions are shown as sentences and are not changed here. Only where each one leads can be. -->
		{#each currentState.rules as rule, index (index)}
			<div class="govuk-form-group">
				<label class="govuk-label govuk-label--s" for="{fieldId}-rule-{index}">If {describeCondition(rule.when)}</label>
				<select class="govuk-select state-editor__select" id="{fieldId}-rule-{index}" bind:value={draftRuleTargets[index]}>
					{#each nextChoices as target (target.stateId)}
						<option value={target.stateId}>{target.label}</option>
					{/each}
				</select>
			</div>
		{/each}

		<div class="govuk-form-group">
			<label class="govuk-label govuk-label--s" for="{fieldId}-default">Otherwise</label>
			<select class="govuk-select state-editor__select" id="{fieldId}-default" bind:value={draftDefault}>
				{#each nextChoices as target (target.stateId)}
					<option value={target.stateId}>{target.label}</option>
				{/each}
			</select>
		</div>
	{/if}

	<div class="state-editor__buttons">
		<button type="submit" class="govuk-button govuk-!-margin-bottom-0">Apply changes</button>
		<button type="button" class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0" onclick={onClose}>
			Cancel
		</button>
	</div>
</form>

<style>
	.state-editor {
		padding: 15px;
	}

	/* The list of choices stays inside the panel, however long a title is. */
	.state-editor__select {
		max-width: 100%;
	}

	.state-editor__buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 15px;
	}
</style>
