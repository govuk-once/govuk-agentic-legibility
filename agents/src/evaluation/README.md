# Conversation fixtures

The JSON files in `fixtures/` are version-controlled inputs for demonstrations and
automated evaluation runs. They are not tied to SvelteKit: the Python fixture repository
loads the same transcripts for the HTTP application and future evaluation runners.

Each fixture contains:

- a stable ID and explicit version;
- the journey it applies to;
- a fixed user-visible conversation;
- optional expected interaction outputs for later automated scoring.

The source conversation is immutable during a run. New user messages added after the
journey starts are stored separately and appended only to the assistant context. Agent
proposals and executor events belong in the run trace, not in the conversation fixture.
