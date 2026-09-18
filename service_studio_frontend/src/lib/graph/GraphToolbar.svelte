<script lang="ts">
	import type { ArmedTool } from './types';

	interface Props {
		armedTool: ArmedTool;
		onarm: (tool: ArmedTool) => void;
	}

	let { armedTool, onarm }: Props = $props();

	const TOOLS: { value: Exclude<ArmedTool, null>; label: string }[] = [
		{ value: 'step', label: 'Step' },
		{ value: 'condition', label: 'Condition' },
		{ value: 'start', label: 'Start' },
		{ value: 'end', label: 'End' }
	];

	/**
	 * Arming the already armed tool disarms it, since click to arm then click a target is a one shot
	 * action with no other way to back out of it short of Escape.
	 */
	function toggle(tool: Exclude<ArmedTool, null>) {
		onarm(armedTool === tool ? null : tool);
	}
</script>

<!-- A step is placed with the existing Add a step control in the panel, these buttons place everything
	that is not already reachable that way: a branch route, or a new entry point or ending. -->
<nav class="graph-toolbar" aria-label="Add to the journey">
	{#each TOOLS as tool (tool.value)}
		<button
			type="button"
			class="graph-toolbar__button"
			class:graph-toolbar__button--armed={armedTool === tool.value}
			aria-pressed={armedTool === tool.value}
			onclick={() => toggle(tool.value)}
		>
			<span class="graph-toolbar__icon graph-toolbar__icon--{tool.value}" aria-hidden="true"></span>
			{tool.label}
		</button>
	{/each}
	<p class="graph-toolbar__heading" aria-hidden="true">Add Node</p>
</nav>

<style>
	/* Wide enough that a centred 36px icon lands with roughly 40px either side, the same inset the page
		title and GOV.UK logo use, so the shapes line up under them rather than sitting hard against the
		left edge of the page. */
	.graph-toolbar {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 120px;
		flex-shrink: 0;
		padding-top: 16px;
		gap: 10px;
		background-color: #fafafa;
		border-right: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.graph-toolbar__heading {
		margin: 0;
		margin-top: 10px;
		font-size: 0.8125rem;
		font-weight: 400;
		color: #505a5f;
	}

	.graph-toolbar__button {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 5px;
		width: 100%;
		padding: 4px 2px;
		background: none;
		border: 1px solid transparent;
		font-family: inherit;
		font-size: 0.8125rem;
		color: #505a5f;
		cursor: pointer;
	}

	.graph-toolbar__button:focus-visible {
		outline: 3px solid #ffdd00;
		outline-offset: 2px;
	}

	.graph-toolbar__button--armed {
		background-color: #e1edf8;
		border-color: #1d70b8;
	}

	.graph-toolbar__icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 44px;
		height: 34px;
	}

	.graph-toolbar__icon--step::before {
		content: '';
		box-sizing: border-box;
		width: 26px;
		height: 18px;
		border: 1px solid #b1b4b6;
		background-color: #ffffff;
	}

	.graph-toolbar__icon--condition::before {
		content: '';
		width: 22px;
		height: 22px;
		background-color: #ffdd00;
		transform: rotate(45deg);
	}

	.graph-toolbar__icon--start::before {
		content: '';
		border-radius: 50%;
		width: 26px;
		height: 26px;
		background-color: #0b0c0c;
	}

	.graph-toolbar__icon--end::before {
		content: '';
		box-sizing: border-box;
		border-radius: 50%;
		width: 26px;
		height: 26px;
		background-color: #00703c;
		border: 2px solid #0b0c0c;
	}
</style>
