<script lang="ts">
	// The title at the top of every step of a review: the name of what is reviewed, the name of the review, and one
	// line saying what the review is for.
	let { caption, heading, intro }: { caption: string; heading: string; intro: string } = $props();
</script>

<div class="review-page-title govuk-!-padding-top-6">
	<span class="govuk-caption-m govuk-!-margin-bottom-2">{caption}</span>
	<h1 class="govuk-heading-xl govuk-!-margin-bottom-2">{heading}</h1>
	<p class="govuk-body govuk-!-margin-bottom-0">{intro}</p>
</div>

<style>
	/* Lines the title up with GOV.UK in the header. */
	.review-page-title {
		padding-inline: 40px;
	}

	@media (max-width: 640px) {
		.review-page-title {
			padding-inline: 15px;
		}
	}
</style>
