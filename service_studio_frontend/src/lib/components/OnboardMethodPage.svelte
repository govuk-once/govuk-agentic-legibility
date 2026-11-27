<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { draftMethodField, type DraftMethod } from '$lib/components/draft-methods';

	/*
		The first page of onboarding, where a person chooses how the draft is made. The route gives the words about
		each choice it offers, so each kind of draft has a method page of its own. The choice is sent back to this
		page, and the route's loader sends the person on to the page for it.
	*/

	interface Props {
		// The link to the page before this one, which the back link leads to. The page that shows this one resolves it.
		backHref: ResolvedPathname;
		caption: string;
		// What drafting with the assistant does, in the words of the route's own kind of draft.
		automationHint: string;
		// Starting from something that already exists. A kind of draft that has nothing to start from leaves it out.
		existingOption?: { label: string; hint: string };
	}

	let { backHref, caption, automationHint, existingOption }: Props = $props();

	// One choice on the page. A choice that is not available yet is shown switched off.
	type MethodOption = { value: DraftMethod; label: string; hint: string; recommended?: boolean; disabled?: boolean };

	const options = $derived<MethodOption[]>([
		{ value: 'automation', label: 'Draft it with automation', hint: automationHint, recommended: true },
		...(existingOption ? [{ value: 'existing' as const, ...existingOption }] : []),
		{
			value: 'blank',
			label: 'Start with a blank graph',
			hint: 'Build the journey yourself from scratch. This option is not available yet.',
			disabled: true
		}
	]);
</script>

<ServiceHeader />

<main class="onboard-method govuk-!-padding-top-9 govuk-!-padding-bottom-9">
	<div class="onboard-method__content">
		<a class="govuk-back-link govuk-!-margin-bottom-5" href={backHref}>Back</a>

		<!-- Sent back to this page, whose loader reads the choice and moves on. A plain GET form needs no script. -->
		<form method="GET">
			<fieldset class="govuk-fieldset">
				<legend class="govuk-fieldset__legend">
					<span class="govuk-caption-l govuk-!-margin-bottom-5">{caption}</span>
					<h1 class="govuk-heading-xl govuk-!-margin-bottom-5">How do you want to draft it?</h1>
				</legend>

				<!-- GOV.UK radios preserve familiar selection, focus and disabled behaviour within the larger choice cards. -->
				<div class="govuk-radios govuk-radios--small draft-methods govuk-!-margin-bottom-5">
					{#each options as option (option.value)}
						<div class="draft-method govuk-!-padding-5">
							<div class="govuk-radios__item govuk-!-margin-bottom-0">
								<input
									class="govuk-radios__input"
									id="draft-method-{option.value}"
									name={draftMethodField}
									type="radio"
									value={option.value}
									aria-describedby="draft-method-{option.value}-hint"
									required
									disabled={option.disabled}
								/>
								<label class="govuk-label govuk-radios__label" for="draft-method-{option.value}">
									<span class="draft-method__heading">
										<span class="govuk-heading-m govuk-!-margin-bottom-0">{option.label}</span>
										{#if option.recommended}
											<strong class="govuk-tag govuk-tag--blue">Recommended</strong>
										{/if}
									</span>
								</label>
								<div id="draft-method-{option.value}-hint" class="govuk-hint govuk-radios__hint govuk-!-margin-top-2">
									{option.hint}
								</div>
							</div>
						</div>
					{/each}
				</div>
			</fieldset>

			<button class="govuk-button" type="submit">Continue</button>
		</form>
	</div>
</main>

<style>
	/* The left edge matches the Service Studio name in the shared header so the two screens use one visual column. */
	.onboard-method {
		margin-left: 145px;
	}

	.onboard-method__content {
		max-width: 640px;
	}

	.draft-methods {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.draft-method {
		box-sizing: border-box;
		border: 2px solid #b1b4b6;
	}

	.draft-method__heading {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 20px;
		width: 100%;
	}

	.draft-method :global(.govuk-radios__label) {
		flex: 1 1 0;
		max-width: none;
	}

	.draft-method :global(.govuk-radios__hint) {
		box-sizing: border-box;
		flex: 0 0 100%;
		max-width: none;
	}

	.draft-method:has(.govuk-radios__input:checked) {
		border: 4px solid #1d70b8;
	}

	.draft-method:has(.govuk-radios__input:disabled) {
		background-color: #f3f2f1;
	}

	/* Unfocused pointer hover remains plain so only an active focus state receives the GOV.UK yellow ring. */
	.draft-method :global(.govuk-radios__item:hover .govuk-radios__input:not(:disabled):not(:focus) + .govuk-radios__label::before) {
		box-shadow: none;
		border-width: 2px;
	}

	/* This corrects an invalid focused hover shadow in gov.css so active focus remains yellow instead of reverting to grey. */
	.draft-method :global(.govuk-radios__input:focus + .govuk-radios__label::before),
	.draft-method :global(.govuk-radios__item:hover .govuk-radios__input:not(:disabled):focus + .govuk-radios__label::before) {
		border-width: 4px;
		box-shadow: 0 0 0 4px #ffdd00;
	}

	@media (max-width: 640px) {
		.onboard-method {
			padding-right: 15px;
			padding-left: 15px;
			margin-left: 0;
		}

		.draft-method__heading {
			align-items: flex-start;
			flex-direction: column;
			gap: 10px;
		}
	}
</style>
