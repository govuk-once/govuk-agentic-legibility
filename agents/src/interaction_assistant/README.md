# Interaction assistant

This package adds bounded agent support to one current service interaction. It does not
navigate a workflow and it is not given the journey continuation token or next
operation.

The framework-neutral `InteractionAssistant` interface accepts:

- the complete user-visible conversation available to the run;
- the current interaction and its JSON Schema;
- an explicit trigger distinguishing a newly opened interaction from a new user message;
- a run-scoped context exposing bounded journey-guidance operations and trace recording.

It returns an ordered list containing one or two structured actions:

- `propose_values` for a safe complete or partial field proposal;
- `no_safe_suggestion` when no current field can be populated safely;
- `answer_journey_question` for a question about the active journey or current step.

The initial implementation uses Strands with one Amazon Bedrock model. The prompt is
version controlled in `prompts/value_proposals.txt`; returned form values are validated
again against the current interaction schema before the application accepts them.

## Progressive-disclosure guidance

For journey questions, the Strands assistant receives two bounded tools:

- `list_journey_guidance`, which retrieves the compact topic directory advertised in the
  journey catalogue;
- `get_journey_guidance`, which retrieves one Markdown document using a topic ID from
  that directory.

The model is prompted to inspect the directory and retrieve relevant guidance before
answering. The application records requested, completed and failed tool calls, together
with the underlying journey-service HTTP exchanges.

Retrieval is deliberately not enforced as a runtime precondition. An
`answer_journey_question` action produced without a guidance request is returned to the
consumer and marked in the trace as not grounded in retrieved guidance. Automated evals
can therefore distinguish successful retrieval from the model answering from parametric
memory without losing the rest of the run.

Retrieved document IDs, versions and SHA-256 hashes are attached by the application,
not reported by the model.

## Local Bedrock configuration

Set the model used for interaction assistance in `agents/.env`:

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

The assistant is created when the Python API starts. Restart the API after changing
these values.

The deterministic executor does not depend on the assistant. When no model is
configured, manual journey execution remains available and run responses expose that
automatic assistance is unavailable.

## Conversation fixtures

Version-controlled conversations live in `agents/src/evaluation/fixtures/`. The same
fixture loader is used by the demonstration frontend and can be used directly by future
automated evaluation runners. The assistant receives the complete conversation at every
interaction; it does not receive earlier value proposals as conversation messages.

A guidance answer that is actually shown to the user is appended as an assistant
conversation message so a later follow-up can refer to it.

## Invocation triggers

Every assistant invocation records why it occurred:

- `interaction_opened` asks the assistant only to propose values for the new form. Earlier
  journey questions must not be answered again;
- `user_message_added` asks the assistant to respond specifically to the newly submitted
  message, using guidance tools when that message is a journey question.

The first action schema permits only one action at a time. When a new message both asks a
question and expresses a form preference, the assistant answers the question but must not
claim that it changed the form. Proposed values remain visible directly in the form, so
the frontend does not render a separate generic “suggestions updated” notice.
