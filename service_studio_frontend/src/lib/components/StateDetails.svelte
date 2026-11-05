<script lang="ts">
	import type { StateDescription } from '$lib/graph/describe-state';
	import type { TargetOption } from '$lib/graph/state-rows';
	import type { State } from '$lib/schema/workflow/process';
	import type { WorkflowIssue } from '$lib/schema/workflow/validate';
	import StateEditor from './StateEditor.svelte';

	interface Props {
		title: string;
		description: StateDescription;
		// The state itself, which the edit form starts from.
		currentState: State;
		// Every state that a route could lead to, named for a list of choices in the edit form.
		targets: TargetOption[];
		// True when no route leads to this state from the start, so it can never run.
		unreachable: boolean;
		// Called with the changed state when an edit is applied. It returns any problems the schema found.
		onApply: (updated: State) => WorkflowIssue[];
		// Called with the id of a state when one of its routes is chosen, so the panel can show that state next.
		onSelectState: (stateId: string) => void;
		// Called with the id of the process an invoke state runs, when its open button is chosen.
		onOpenProcess: (processId: string) => void;
		onClose: () => void;
	}

	let { title, description, currentState, targets, unreachable, onApply, onSelectState, onOpenProcess, onClose }: Props = $props();

	// Whether the edit form is open in place of the details. The panel is shown afresh for each state, so a
	// form left open never carries over to another state.
	let editing = $state(false);

	// The facts that explain the state are shown at once, unless one only repeats the title, as the
	// question of an input usually does. Everything else is behind the More detail fold.
	const mainFacts = $derived(description.facts.filter((fact) => fact.main && fact.value !== title));
	const moreFacts = $derived(description.facts.filter((fact) => !fact.main));
</script>

{#if editing}
	<div class="state-details__editing">
		<h2 class="govuk-heading-s state-details__editing-title">{title}</h2>
		<StateEditor {currentState} stateCode={description.code} {targets} {onApply} onClose={() => (editing = false)} />
	</div>
{:else}
	<div class="state-details">
		<div class="state-details__header">
			<h2 class="govuk-heading-s govuk-!-margin-bottom-0">{title}</h2>
			<div class="state-details__actions">
				<button type="button" class="govuk-link govuk-body state-details__link" onclick={() => (editing = true)}>
					Edit
				</button>
				<button type="button" class="govuk-link govuk-body state-details__link" onclick={onClose}>Close</button>
			</div>
		</div>

		{#if unreachable}
			<div class="govuk-inset-text">Nothing leads to this step, so it can never run.</div>
		{/if}

		{#if mainFacts.length > 0}
			<dl class="state-details__facts">
				{#each mainFacts as fact, index (index)}
					<div>
						<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">{fact.label}</dt>
						<dd class="govuk-body govuk-!-margin-bottom-2 state-details__value">{fact.value}</dd>
					</div>
				{/each}
			</dl>
		{/if}

		{#if description.opensProcess}
			<button
				type="button"
				class="govuk-button govuk-button--secondary"
				onclick={() => description.opensProcess && onOpenProcess(description.opensProcess.id)}
			>
				Open {description.opensProcess.title}
			</button>
		{/if}

		{#if description.routes.length > 0}
			<h3 class="govuk-heading-s govuk-!-margin-bottom-2">Where it goes next</h3>
			<ul class="govuk-list">
				{#each description.routes as route, index (index)}
					<li>
						<span class="state-details__route-label">{route.label}</span>
						<button type="button" class="govuk-link state-details__link" onclick={() => onSelectState(route.targetId)}>
							{route.targetTitle}
						</button>
					</li>
				{/each}
			</ul>
		{/if}

		<details class="govuk-details">
			<summary class="govuk-details__summary">
				<span class="govuk-details__summary-text">More detail</span>
			</summary>
			<div class="govuk-details__text">
				<dl class="state-details__facts">
					<div>
						<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">Type</dt>
						<dd class="govuk-body govuk-!-margin-bottom-2">{description.type}</dd>
					</div>
					<div>
						<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">Code</dt>
						<dd class="govuk-body govuk-!-margin-bottom-2">{description.code}</dd>
					</div>
					{#each moreFacts as fact, index (index)}
						<div>
							<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">{fact.label}</dt>
							<dd class="govuk-body govuk-!-margin-bottom-2 state-details__value">{fact.value}</dd>
						</div>
					{/each}
				</dl>
			</div>
		</details>
	</div>
{/if}

<style>
	.state-details {
		padding: 15px;
	}

	.state-details__actions {
		display: flex;
		gap: 15px;
	}

	.state-details__editing-title {
		margin: 0;
		padding: 15px 15px 0;
	}

	.state-details__header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 15px;
	}

	.state-details__facts {
		margin: 0 0 15px;
	}

	/* A long value, such as a message, wraps inside the panel and keeps the line breaks it was written with. */
	.state-details__value {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.state-details__route-label {
		display: block;
		color: #505a5f;
	}

	/* A button that looks like a link. It is a button because it acts on the page and does not go to a new one. */
	.state-details__link {
		padding: 0;
		background: none;
		border: 0;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
</style>
