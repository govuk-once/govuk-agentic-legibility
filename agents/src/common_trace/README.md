# Common trace converter

Convert implementation-specific journey JSONL traces into a small, ordered common
trace containing positive, externally meaningful events.

```bash
uv run python -m agents.src.common_trace .traces \
  --output-dir .common-traces
```

The default output is YAML. Use `--format json` for JSON and `--overwrite` to replace
existing outputs.

A raw trace without a terminal event is converted with `run.status: incomplete`. The
converter does not fail merely because a journey stopped part-way through.

The common trace deliberately omits implementation mechanics such as agent invocation
triggers, proposal-review flags, directory-listing tool calls and HTTP transport
details. The `source_trace` field points back to the complete raw JSONL file.

Named starting conversations are referenced under
`initial_context.conversation_fixture`; their messages are not repeated in the common
trace. The fixture or future scenario definition remains the source of test input,
while user messages introduced during a run remain ordered common-trace events.
