<script lang="ts">
	import type { ConditionNodeData } from './types';

	let { data }: { data: ConditionNodeData } = $props();
</script>

<div class="journey-condition-node">
	<!-- SVG preserves the diamond border at every graph zoom level without rotating the question text.
		The shape is sized to hold a two line question at govuk-body-s without the text spilling past the
		sloped edges. -->
	<svg
		class="journey-condition-node__shape"
		width="300"
		height="176"
		viewBox="0 0 300 176"
		xmlns="http://www.w3.org/2000/svg"
		aria-hidden="true"
	>
		<path d="M150 3 L297 88 L150 173 L3 88 Z" fill="#fff7bf" stroke="#0b0c0c" stroke-width="2" />
	</svg>
	<p class="journey-condition-node__question govuk-body-s govuk-!-font-weight-bold govuk-!-margin-bottom-0">
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
		width: 300px;
		height: 176px;
		font-family: 'GDS Transport', arial, sans-serif;
		color: #0b0c0c;
	}

	.journey-condition-node__shape {
		position: absolute;
		inset: 0;
	}

	.journey-condition-node__question {
		position: relative;
		width: 200px;
		text-align: center;
	}
</style>
