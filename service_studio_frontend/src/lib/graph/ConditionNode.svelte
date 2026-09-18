<script lang="ts">
	let { ariaLabel }: { ariaLabel: string } = $props();
</script>

<!-- A plain diamond, no text: the route it stands for is named on the step that owns it and edited in
	the step editor's branch routes, so repeating that wording here only duplicated it. -->
<div class="journey-condition-node" role="img" aria-label={ariaLabel}>
	<div class="journey-condition-node__shape"></div>
</div>

<style>
	.journey-condition-node {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 40px;
		height: 40px;
	}

	.journey-condition-node__shape {
		width: 28px;
		height: 28px;
		background-color: #ffdd00;
		transform: rotate(45deg);
	}
</style>
