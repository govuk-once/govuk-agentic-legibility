<script lang="ts">
	import type { ConditionNodeData } from './types';

	let { data }: { data: ConditionNodeData } = $props();
</script>

<div class="journey-condition-node">
	<!-- SVG preserves the diamond border at every graph zoom level without rotating the question text. -->
	<svg
		class="journey-condition-node__shape"
		width="240"
		height="140"
		viewBox="0 0 240 140"
		xmlns="http://www.w3.org/2000/svg"
		aria-hidden="true"
	>
		<path d="M120 2 L238 70 L120 138 L2 70 Z" fill="#fff7bf" stroke="#0b0c0c" stroke-width="2" />
	</svg>
	<p class="journey-condition-node__question govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">
		{data.question}
	</p>
</div>

<style>
	.journey-condition-node {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		width: 240px;
		height: 140px;
		font-family: 'GDS Transport', arial, sans-serif;
		color: #0b0c0c;
	}

	.journey-condition-node__shape {
		position: absolute;
		inset: 0;
	}

	.journey-condition-node__question {
		position: relative;
		width: 150px;
		text-align: center;
	}
</style>
