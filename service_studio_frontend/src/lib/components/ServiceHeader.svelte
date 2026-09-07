<!-- Branding and prototype status remain in a shared header so every editor route can identify its context. -->
<header class="service-header">
	<!-- The service name follows the divider so the GOV.UK identity remains distinct. -->
	<div class="service-header__branding">
		<span class="service-header__logo">GOV.UK</span>
		<span class="service-header__divider"></span>
		<span class="govuk-body govuk-!-font-size-19 govuk-!-margin-bottom-0">Service Studio</span>
	</div>
	<strong class="service-header__prototype-flag">Experimental prototype</strong>
</header>

<style>
	.service-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 15px 40px;
		background-color: #ffffff;
		border-bottom: 1px solid #b1b4b6;
	}

	.service-header__branding {
		display: flex;
		align-items: center;
		gap: 15px;
	}

	.service-header__logo {
		font-family: 'GDS Transport', arial, sans-serif;
		font-size: 1.25rem;
		font-weight: 700;
		line-height: 1.2;
		color: #0b0c0c;
	}

	.service-header__divider {
		width: 1px;
		height: 22px;
		background-color: #b1b4b6;
	}

	.service-header__prototype-flag {
		font-family: 'GDS Transport', arial, sans-serif;
		font-size: 1rem;
		font-weight: 400;
		line-height: 1.25;
		color: #ffffff;
		background-color: #1d70b8;
		padding: 4px 10px;
	}

	@media (max-width: 640px) {
		.service-header {
			align-items: flex-start;
			flex-direction: column;
			gap: 15px;
			padding: 15px;
		}
	}
</style>
