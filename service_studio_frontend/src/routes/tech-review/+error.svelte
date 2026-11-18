<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import DraftProblemPage from '$lib/components/DraftProblemPage.svelte';

	// The technical review stops here when its form cannot be opened. A form whose problems were listed did not match
	// the schema, and any other error means there was no form to open.
	const issues = $derived(page.error?.issues);
</script>

<DraftProblemPage problem={issues ? { ok: false, reason: 'invalid', issues } : { ok: false, reason: 'missing' }} startHref={resolve('/edit-form')} title="Technical review">
	{#snippet missing()}
		<h1 class="govuk-heading-xl">Nothing to review yet</h1>
		<p class="govuk-body">
			There is no form in this browser tab. <a class="govuk-link" href={resolve('/edit-form')}>Open a form</a>, edit it and
			send it to tech review to review it here.
		</p>
	{/snippet}
</DraftProblemPage>
