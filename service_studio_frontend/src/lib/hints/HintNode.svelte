<script lang="ts">
	import type { Node, NodeProps } from '@xyflow/svelte';
	import { hintBracketWidth, hintLineLength, hintNoteWidth, type HintNodeData } from './hint-nodes';

	let { data }: NodeProps<Node<HintNodeData>> = $props();
</script>

<!--
	A best practice hint beside the shapes it is about: a bracket as tall as the shapes, a dotted line from the middle
	of the bracket, and a note with a light bulb, the hint's title and its advice. The note is centred on the bracket,
	so it can be taller than the shapes beside it. On the left of the shapes the hint is drawn the other way round,
	with the bracket on its right.
-->
<div class="hint-node" class:hint-node--left={data.side === 'left'} style:--hint-bracket-width="{hintBracketWidth}px" style:--hint-line-length="{hintLineLength}px" style:--hint-note-width="{hintNoteWidth}px">
	<span class="hint-node__bracket"></span>
	<span class="hint-node__line"></span>
	<div class="hint-node__note">
		<p class="govuk-body-s govuk-!-font-weight-bold govuk-!-margin-bottom-1 hint-node__title">
			<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
				<path d="M8 1.5a4.5 4.5 0 0 0-2.4 8.3c.5.4.9 1 .9 1.7h3c0-.7.4-1.3.9-1.7A4.5 4.5 0 0 0 8 1.5z" fill="none" stroke="currentColor" stroke-width="1.4" />
				<path d="M6.5 13.5h3M7 15h2" fill="none" stroke="currentColor" stroke-width="1.4" />
			</svg>
			{data.title}
		</p>
		<p class="govuk-body-s govuk-!-margin-bottom-0">{data.advice}</p>
	</div>
</div>

<style>
	.hint-node {
		position: relative;
		width: 100%;
		height: 100%;
		pointer-events: none;
	}

	/* An open bracket down the right side of the shapes, as tall as they are. */
	.hint-node__bracket {
		position: absolute;
		top: 0;
		bottom: 0;
		left: 0;
		width: var(--hint-bracket-width);
		box-sizing: border-box;
		border: 2px solid #5694ca;
		border-left: 0;
	}

	.hint-node__line {
		position: absolute;
		top: 50%;
		left: var(--hint-bracket-width);
		width: var(--hint-line-length);
		border-top: 1px dotted #5694ca;
	}

	/* The note is centred on the middle of the bracket, beside the dotted line. */
	.hint-node__note {
		position: absolute;
		top: 50%;
		left: calc(var(--hint-bracket-width) + var(--hint-line-length));
		width: var(--hint-note-width);
		box-sizing: border-box;
		padding: 10px 15px;
		background-color: #eaf2fb;
		border-left: 3px solid #1d70b8;
		transform: translateY(-50%);
	}

	/* On the left of the shapes, the bracket opens to the right and the note is on the far left. */
	.hint-node--left .hint-node__bracket {
		left: auto;
		right: 0;
		border-left: 2px solid #5694ca;
		border-right: 0;
	}

	.hint-node--left .hint-node__line {
		left: auto;
		right: var(--hint-bracket-width);
	}

	.hint-node--left .hint-node__note {
		left: 0;
	}

	.hint-node__title {
		display: flex;
		align-items: center;
		gap: 5px;
		color: #003078;
	}

	.hint-node__title svg {
		flex-shrink: 0;
		color: #1d70b8;
	}
</style>
