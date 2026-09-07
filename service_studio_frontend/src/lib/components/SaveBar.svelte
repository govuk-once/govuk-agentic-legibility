<!-- Save controls and status share a footer so the result of editing remains visible beside the actions. -->
<footer class="save-bar">
	<div class="save-bar__actions">
		<button class="govuk-button save-bar__submit" type="button">Save and continue</button>
		<a class="govuk-link" href="#top">Save as draft</a>
	</div>
	<!-- Status explains recency and publishing safety before a user continues. -->
	<p class="save-bar__status">Last saved 2 minutes ago · nothing goes live until policy sign-off</p>
</footer>

<style>
	.save-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 20px 40px;
		background-color: #f3f2f1;
		border-top: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.save-bar__actions {
		display: flex;
		align-items: center;
		gap: 20px;
	}

	.save-bar__submit {
		margin-bottom: 0;
	}

	.save-bar__status {
		margin: 0;
		font-size: 1rem;
		line-height: 1.2;
		color: #505a5f;
	}
</style>
