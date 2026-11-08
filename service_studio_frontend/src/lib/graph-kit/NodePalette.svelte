<script lang="ts">
	// One shape that can be dragged from the palette onto the canvas. The value says which shape it is, and
	// is what the canvas reads from the drop to know what to add.
	export type PaletteTool = { value: string; label: string; shape: 'step' | 'condition' | 'start' | 'end' };

	interface Props {
		// The shapes offered. The editor says which, so an editor that only allows some of them shows only those.
		tools: PaletteTool[];
	}

	let { tools }: Props = $props();

	/**
	 * Marks the drag as carrying one of the shapes, so the canvas only reacts to a drop that came from here and
	 * not to some other kind of drag the browser also fires this event for.
	 */
	function handleDragStart(event: DragEvent, tool: PaletteTool) {
		event.dataTransfer?.setData('application/x-journey-node', tool.value);
		if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
	}
</script>

<nav class="node-palette" aria-label="Add to the journey">
	{#each tools as tool (tool.value)}
		<div
			class="node-palette__item"
			role="button"
			tabindex="0"
			draggable="true"
			ondragstart={(event) => handleDragStart(event, tool)}
			aria-label="{tool.label}, drag onto the canvas to add"
		>
			<span class="node-palette__icon node-palette__icon--{tool.shape}" aria-hidden="true"></span>
			{tool.label}
		</div>
	{/each}
	<p class="govuk-body node-palette__heading">Add node</p>
</nav>

<style>
	/* Wide enough that a centred icon sits with an even gap either side. */
	.node-palette {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 120px;
		flex-shrink: 0;
		padding-top: 15px;
		gap: 10px;
		background-color: #f3f2f1;
		border-right: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.node-palette__heading {
		margin: 0;
		color: #505a5f;
	}

	.node-palette__item {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 5px;
		width: 100%;
		padding: 5px 0;
		font-size: 1rem;
		color: #0b0c0c;
		cursor: grab;
	}

	.node-palette__item:focus-visible {
		outline: 3px solid #ffdd00;
		outline-offset: 2px;
	}

	.node-palette__icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 44px;
		height: 34px;
	}

	.node-palette__icon--step::before {
		content: '';
		box-sizing: border-box;
		width: 26px;
		height: 18px;
		border: 1px solid #b1b4b6;
		background-color: #ffffff;
	}

	.node-palette__icon--condition::before {
		content: '';
		width: 22px;
		height: 22px;
		background-color: #ffdd00;
		transform: rotate(45deg);
	}

	.node-palette__icon--start::before {
		content: '';
		border-radius: 50%;
		width: 26px;
		height: 26px;
		background-color: #0b0c0c;
	}

	.node-palette__icon--end::before {
		content: '';
		box-sizing: border-box;
		border-radius: 50%;
		width: 26px;
		height: 26px;
		background-color: #00703c;
		border: 2px solid #0b0c0c;
	}

	/* On a narrow screen the palette lies along the top of the canvas instead of down its side. */
	@media (max-width: 900px) {
		.node-palette {
			flex-direction: row;
			flex-wrap: wrap;
			justify-content: center;
			width: auto;
			padding: 10px;
			border-right: 0;
			border-bottom: 1px solid #b1b4b6;
		}

		.node-palette__item {
			width: auto;
			padding: 5px 15px;
		}
	}
</style>
