<script lang="ts">
	import type { WorkingState } from '$lib/schema/workflow/working-process';
	import { moduleTileFor } from './module-catalogue';
	import ModuleIcon from './ModuleIcon.svelte';

	/*
		A line on the card of a state saying which module it came from, beside the module's icon in the same grey square
		the menu draws it in. A state that was not added with a module shows nothing.
	*/
	interface Props {
		currentState: WorkingState;
	}

	let { currentState }: Props = $props();

	const group = $derived(currentState.metadata?.group);
	const tile = $derived(typeof group === 'string' ? moduleTileFor(group) : undefined);
</script>

{#if tile}
	<p class="govuk-body govuk-!-margin-bottom-0 module-note">
		<span class="module-note__icon"><ModuleIcon name={tile.key} /></span>
		<span>This state belongs to the {tile.label} module. Deleting it removes the whole module.</span>
	</p>
{/if}

<style>
	/* The square keeps its size when the words beside it wrap. */
	.module-note {
		display: flex;
		align-items: center;
		gap: 15px;
		color: #505a5f;
	}

	/* The same grey square as a tile in the module menu, so the module is recognised from the menu. */
	.module-note__icon {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		width: 44px;
		height: 44px;
		color: #3f484c;
		background-color: #f3f2f1;
		border-radius: 9px;
	}
</style>
