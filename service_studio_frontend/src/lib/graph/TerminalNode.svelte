<script lang="ts">
	import type { TerminalNodeData } from './types';

	let { data }: { data: TerminalNodeData } = $props();
</script>

<!-- Start and end share one component because their content is otherwise identical, differing only by the
	appearance modifier that sets the fill and, for the end event, the thick ring. Circles with the label
	inside follow the BPMN convention for start and end events. -->
<div
	class="journey-terminal-node journey-terminal-node--{data.appearance} govuk-body-s govuk-!-font-weight-bold govuk-!-margin-bottom-0"
>
	{data.label}
</div>

<style>
	.journey-terminal-node {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 72px;
		height: 72px;
		border-radius: 50%;
		font-family: 'GDS Transport', arial, sans-serif;
		color: #ffffff;
	}

	.journey-terminal-node--start {
		background-color: #0b0c0c;
	}

	/* The thick black ring is the BPMN end event marker, so end reads as a distinct shape from start
		rather than only a different colour. */
	.journey-terminal-node--end {
		background-color: #00703c;
		border: 4px solid #0b0c0c;
	}
</style>
