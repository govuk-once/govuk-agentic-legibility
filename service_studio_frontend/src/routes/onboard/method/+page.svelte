<script lang="ts">
	import { resolve } from '$app/paths';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
</script>

<svelte:head>
	<title>Choose a drafting method | Service Studio</title>
</svelte:head>

<ServiceHeader />

<main class="onboard-method govuk-!-padding-top-9 govuk-!-padding-bottom-9">
	<div class="onboard-method__content">
			<a class="govuk-back-link govuk-!-margin-bottom-5" href={resolve('/onboard')}>Back</a>

			<form method="GET" action={resolve('/onboard/details')}>
				<fieldset class="govuk-fieldset">
					<legend class="govuk-fieldset__legend">
						<span class="govuk-caption-l govuk-!-margin-bottom-5">Start a new service, step 1 of 2</span>
						<h1 class="govuk-heading-xl govuk-!-margin-bottom-5">How do you want to draft it?</h1>
					</legend>

					<!-- GOV.UK radios preserve familiar selection, focus and disabled behaviour within the larger choice cards. -->
					<div class="govuk-radios govuk-radios--small draft-methods govuk-!-margin-bottom-5">
						<div class="draft-method govuk-!-padding-5">
							<div class="govuk-radios__item govuk-!-margin-bottom-0">
								<input
									class="govuk-radios__input"
									id="draft-method-automation"
									name="draft-method"
									type="radio"
									value="automation"
									aria-describedby="draft-method-automation-hint"
									required
								/>
								<label class="govuk-label govuk-radios__label" for="draft-method-automation">
									<span class="draft-method__heading">
										<span class="govuk-heading-m govuk-!-margin-bottom-0">Draft it with automation</span>
										<strong class="govuk-tag govuk-tag--blue">Recommended</strong>
									</span>
								</label>
								<div id="draft-method-automation-hint" class="govuk-hint govuk-radios__hint govuk-!-margin-top-2">
									An assistant reads what is already on GOV.UK, plus anything you give it, and drafts a service journey and graph. Steps and conditions remain editable until published.
								</div>
							</div>
						</div>

						<div class="draft-method govuk-!-padding-5">
							<div class="govuk-radios__item govuk-!-margin-bottom-0">
								<input
									class="govuk-radios__input"
									id="draft-method-blank"
									name="draft-method"
									type="radio"
									value="blank"
									aria-describedby="draft-method-blank-hint"
									disabled
								/>
								<label class="govuk-label govuk-radios__label" for="draft-method-blank">
									<span class="govuk-heading-m govuk-!-margin-bottom-0">Start with a blank graph</span>
								</label>
								<div id="draft-method-blank-hint" class="govuk-hint govuk-radios__hint govuk-!-margin-top-2">
									Build the journey yourself from scratch. This option is not available yet.
								</div>
							</div>
						</div>
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
