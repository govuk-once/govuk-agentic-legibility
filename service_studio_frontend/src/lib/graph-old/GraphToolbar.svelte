<script lang="ts">
	const TOOLS = [
		{ value: 'step', label: 'Step' },
		{ value: 'condition', label: 'Condition' },
		{ value: 'start', label: 'Start' },
		{ value: 'end', label: 'End' }
	] as const;

	/**
	 * Marks the drag as carrying one of the four shapes, rather than some other kind of drag the browser
	 * might also fire this event for, so the canvas only reacts to a drop that actually came from here.
	 * Dropped onto empty canvas, Step places a new, unconnected step there; dropped onto an existing step,
	 * Condition gives that step a second route, Start makes it the journey's entry point, and End clears
	 * its onward routes, the same three actions the step editor panel already offers, just reachable
	 * directly on the canvas too.
	 */
	function handleDragStart(event: DragEvent, tool: (typeof TOOLS)[number]['value']) {
		event.dataTransfer?.setData('application/x-journey-node', tool);
		if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
	}
</script>

<nav class="graph-toolbar" aria-label="Add to the journey">
	{#each TOOLS as tool (tool.value)}
		<div
			class="graph-toolbar__item"
			role="button"
			tabindex="0"
			draggable="true"
			ondragstart={(event) => handleDragStart(event, tool.value)}
			aria-label="{tool.label}, drag onto the canvas to add"
		>
			<span class="graph-toolbar__icon graph-toolbar__icon--{tool.value}" aria-hidden="true"></span>
			{tool.label}
		</div>
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

	.graph-toolbar__item {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 5px;
		width: 100%;
		padding: 4px 2px;
		font-size: 0.8125rem;
		color: #505a5f;
		cursor: grab;
	}

	.graph-toolbar__item:focus-visible {
		outline: 3px solid #ffdd00;
		outline-offset: 2px;
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
