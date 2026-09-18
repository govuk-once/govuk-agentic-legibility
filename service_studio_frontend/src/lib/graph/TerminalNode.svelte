<script lang="ts">
	import type { TerminalNodeData } from './types';

	let { data }: { data: TerminalNodeData } = $props();
</script>

<!-- Start and end share one component because their content is otherwise identical, differing only by
	the appearance modifier that sets the fill and, for the end event, the ring. The circle itself carries
	no text, matching the approved design, its label sits underneath instead. The label is positioned
	absolutely so it does not change the 40px circle the layout measures and edges anchor to. -->
<div class="journey-terminal-node">
	<div class="journey-terminal-node__circle journey-terminal-node__circle--{data.appearance}"></div>
	<span class="journey-terminal-node__label">{data.label}</span>
</div>

<style>
	.journey-terminal-node {
		position: relative;
		box-sizing: border-box;
		width: 40px;
		height: 40px;
	}

	.journey-terminal-node__circle {
		box-sizing: border-box;
		width: 40px;
		height: 40px;
		border-radius: 50%;
	}

	.journey-terminal-node__circle--start {
		background-color: #0b0c0c;
	}

	.journey-terminal-node__circle--end {
		background-color: #00703c;
		border: 3px solid #0b0c0c;
	}

	.journey-terminal-node__label {
		position: absolute;
		top: 46px;
		left: 50%;
		transform: translateX(-50%);
		font-family: 'GDS Transport', arial, sans-serif;
		font-size: 0.875rem;
		font-weight: 400;
		color: #505a5f;
		white-space: nowrap;
	}
</style>
