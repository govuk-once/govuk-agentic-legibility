<script lang="ts">
	// The GOV.UK error message shown above a field that has a problem. Nothing is shown when there is none. The id is
	// the field's id followed by -error, which the field names in its aria-describedby.
	let { field, message }: { field: string; message: string | undefined } = $props();
</script>

{#if message}
	<p id="{field}-error" class="govuk-error-message">
		<span class="govuk-visually-hidden">Error:</span>
		{message}
	</p>
{/if}
