# Agents

## Authentication
The authentication processes here are designed to replicate the existing processes used by Flex developers and detailed
[here](https://gdsgovukagents.atlassian.net/wiki/x/ToC3Cw).

Both of the authentication scripts are in Python. It will help if you run the following in the root directory of
this repository:
```sh
export PYTHONPATH=$(pwd)
```

The project is built with [uv](https://docs.astral.sh/uv/). Make sure it is installed. Run `uv sync` to load all
dependencies.

### Getting a JWT from Flex
Run (from the project root):
```sh
uv run python agents/src/authenticate_flex.py
```

The token will be printed to the console.

### Getting a linking token from the DVLA stub form
You will need a test-user customer id. You can find some candidates
[here](https://gdsgovukagents.atlassian.net/wiki/spaces/AL/pages/191889515/Driving+License+Info+PoC#3.-Get-Linking-IDs.).

Then, in the project root, run:
```sh
uv run python agents/src/authenticate_dvla.py <Customer ID>
```

Again, the required token will be printed to the console.