# Agentic Legibility

## Authentication
The authentication processes here are designed to replicate the existing processes used by Flex developers and detailed
[here](https://gdsgovukagents.atlassian.net/wiki/x/ToC3Cw).

You will need to populate a local `.env` file with various credentials and values. The file format follows that specified
by the Flex team and modelled [here](https://github.com/govuk-once/flex/blob/main/.env.playground.example). To start with, you will need 
[OneLogin credentials](https://gdsgovukagents.atlassian.net/wiki/spaces/AL/pages/191889515/Driving+License+Info+PoC#1.-OneLogin).
Broadly, the steps are:
1. Connect to the VPN.
2. Go to [https://signin.staging.account.gov.uk/enter-email-create]()
3. Follow the link marked “Go to GOV.UK OneLogin”
4. Complete the registration process, making a note of the email address you used and the password. 
    **When completing the 2FA process, do not use the QR code, use the manual process, saving the seed code, which you will need for the `.env` file.**

Ask one of the repository owners for the other configuration elements required for the `.env`.

Both of the authentication scripts are in Python. It will help if you run the following in the root directory of
this repository:
```sh
export PYTHONPATH=$(pwd)
```

The required authentication tokens are saved to Secrets Manager in AWS. You will need a live credential chain to one of the 
AI Legibility accounts for the authentication mechanisms to work.

The project is built with [uv](https://docs.astral.sh/uv/). Make sure it is installed. Run `uv sync` to load all
dependencies.

### Getting a JWT from Flex
Run (from the project root):
```sh
uv run python agents/src/tools/authenticate_flex.py
```

The token will be printed to the console and saved to SecretsManager.

### Getting a linking token from the DVLA stub form
You will need a test-user customer id. You can find some candidates
[here](https://gdsgovukagents.atlassian.net/wiki/spaces/AL/pages/191889515/Driving+License+Info+PoC#3.-Get-Linking-IDs.).

Then, in the project root, run:
```sh
uv run python agents/src/tools/authenticate_dvla.py <Customer ID>
```

Again, the required token will be printed to the console and saved to Secrets Manager.

**Stub server**: a stub server has been created as a substitute for the `flex/dvla` and `flex/udp` endpoints in the event
that the DVLA link process is unavailable. Add `USE_STUB_SERVER=1` to the `.env` file to activate their usage. 