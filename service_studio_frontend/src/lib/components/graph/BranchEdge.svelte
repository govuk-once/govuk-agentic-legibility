<script lang="ts">
	import {
		BaseEdge,
		EdgeLabel,
		getSmoothStepPath,
		type EdgeProps
	} from '@xyflow/svelte';
	import type { BranchEdge } from '$lib/graph/types';

	let {
		id,
		sourceX,
		sourceY,
		targetX,
		targetY,
		sourcePosition,
		targetPosition,
		markerEnd,
		label,
		data
	}: EdgeProps<BranchEdge> = $props();

	let [path, labelX, labelY] = $derived(
		getSmoothStepPath({
			sourceX,
			sourceY,
			targetX,
			targetY,
			sourcePosition,
			targetPosition
		})
	);
</script>

<!-- The base edge keeps branch paths and arrow markers consistent with ordinary journey connections. -->
<BaseEdge {id} {path} {markerEnd} />

{#if label}
	<!-- A custom label is required because the standard edge label cannot receive GOV.UK component classes. -->
	<EdgeLabel x={labelX} y={labelY} transparent>
		<!-- A missing tag colour falls back to grey so a branch label is never left unstyled. -->
		<strong class="govuk-tag govuk-tag--{data?.tagColour ?? 'grey'}">
			{label}
		</strong>
	</EdgeLabel>
{/if}
