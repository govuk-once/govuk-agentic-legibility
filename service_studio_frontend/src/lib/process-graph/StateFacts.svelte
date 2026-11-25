<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { StateDescription } from './describe-state';

	interface Props {
		// The title of the state, used to leave out a fact that only repeats it, as the question of an input does.
		title: string;
		description: StateDescription;
		// True when no route leads to this state from the start, so it can never run.
		unreachable: boolean;
		// Called with the id of a state when one of its routes is chosen, so the panel can show that state next.
		onSelectState: (stateId: string) => void;
		// Called with the id of the process an invoke state runs, when its open button is chosen. An editor that cannot
		// open another process gives none, and the button is left out.
		onOpenProcess?: (processId: string) => void;
		// Anything the editing page wants between the routes and the More detail fold, such as move buttons.
		children?: Snippet;
	}

	let { title, description, unreachable, onSelectState, onOpenProcess, children }: Props = $props();

	// The facts that explain the state are shown at once, unless one only repeats the title. Everything else
	// is behind the More detail fold, so the panel stays short.
	const mainFacts = $derived(description.facts.filter((fact) => fact.main && fact.value !== title));
	const moreFacts = $derived(description.facts.filter((fact) => !fact.main));
</script>

{#if unreachable}
	<div class="govuk-inset-text">Nothing leads to this step, so it can never run.</div>
{/if}

{#if mainFacts.length > 0}
	<dl class="state-facts__list">
		{#each mainFacts as fact, index (index)}
			<div>
				<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">{fact.label}</dt>
				<dd class="govuk-body govuk-!-margin-bottom-2 state-facts__value">{fact.value}</dd>
			</div>
		{/each}
	</dl>
{/if}

{#if description.opensProcess && onOpenProcess}
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
				<span class="state-facts__route-label">{route.label}</span>
				<button type="button" class="govuk-link state-facts__link" onclick={() => onSelectState(route.targetId)}>
					{route.targetTitle}
				</button>
			</li>
		{/each}
	</ul>
{/if}

{@render children?.()}

<details class="govuk-details">
	<summary class="govuk-details__summary">
		<span class="govuk-details__summary-text">More detail</span>
	</summary>
	<div class="govuk-details__text">
		<dl class="state-facts__list">
			<div>
				<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">Type</dt>
				<dd class="govuk-body govuk-!-margin-bottom-2">{description.stateType}</dd>
			</div>
			<div>
				<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">Code</dt>
				<dd class="govuk-body govuk-!-margin-bottom-2">{description.code}</dd>
			</div>
			{#each moreFacts as fact, index (index)}
				<div>
					<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">{fact.label}</dt>
					<dd class="govuk-body govuk-!-margin-bottom-2 state-facts__value">{fact.value}</dd>
				</div>
			{/each}
		</dl>
	</div>
</details>

<style>
	.state-facts__list {
		margin: 0 0 15px;
	}

	/* A long value, such as a message, wraps inside the panel and keeps the line breaks it was written with. */
	.state-facts__value {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.state-facts__route-label {
		display: block;
		color: #505a5f;
	}

	/* A button that looks like a link. It is a button because it acts on the page and does not go to a new one. */
	.state-facts__link {
		padding: 0;
		background: none;
		border: 0;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
</style>
