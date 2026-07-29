# Interaction assistant

This package adds bounded agent support to one current service interaction. It does not
retrieve or navigate a workflow and it is not given the journey continuation token or
next operation.

The framework-neutral `InteractionAssistant` interface accepts:

- the latest user message;
- earlier user-visible conversation;
- the current interaction and its JSON Schema.

It returns one structured action:

- `propose_values` for a safe complete or partial field proposal;
- `no_safe_suggestion` when no current field can be populated safely.

The initial implementation uses Strands with one Amazon Bedrock model. The prompt is
version controlled in `prompts/value_proposals.txt`; the returned values are validated
again against the current interaction schema before the application accepts them.

## Local Bedrock configuration

Set the model used for structured value proposals in `agents/.env`:

```dotenv
JOURNEY_AGENT_MODEL_ID=<Bedrock model or inference-profile ID>
JOURNEY_AGENT_REGION=<AWS region>
```

For example:

```dotenv
JOURNEY_AGENT_MODEL_ID=eu.anthropic.claude-haiku-4-5-20251001-v1:0
JOURNEY_AGENT_REGION=eu-west-2
```

Run the application process with AWS credentials that can invoke that model.

The assistant is created when the Python API starts. Restart the API after
changing these values.

The deterministic executor does not depend on the assistant. When no model is
configured, manual journey execution remains available and the assistance
endpoint returns a configuration error.