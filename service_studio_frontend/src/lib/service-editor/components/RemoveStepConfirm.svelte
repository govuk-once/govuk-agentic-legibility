<script lang="ts">
	interface Props {
		// What is being removed, in the words the person sees on the graph, such as step or decision.
		noun: string;
		onRemove: () => void;
		onCancel: () => void;
	}

	let { noun, onRemove, onCancel }: Props = $props();
</script>

<!-- An inline confirmation, rather than a browser dialog, keeps the interaction in the same GOV.UK styled
	surface. -->
<span class="remove-step-confirm">
	Remove this {noun}?
	<button type="button" class="govuk-link remove-step-confirm__remove" onclick={onRemove}>Remove {noun}</button>
	<button type="button" class="govuk-link" onclick={onCancel}>Keep {noun}</button>
</span>

<style>
	.remove-step-confirm {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 1rem;
		color: #0b0c0c;
	}

	.remove-step-confirm__remove {
		color: #d4351c;
	}

	@media (max-width: 640px) {
		.remove-step-confirm {
			flex-wrap: wrap;
		}
	}
</style>
