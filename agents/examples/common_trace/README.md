# Common trace examples

These files show how observed, implementation-specific journey traces are converted
into the common trace format.

The three examples were selected from completed trace-version 1.5 runs:

- `manual-entry-from-conversation-history` follows the manual-entry branch using only
  information from the starting conversation;
- `postcode-lookup-from-conversation-history` follows the postcode-lookup branch using
  only information from the starting conversation;
- `postcode-question-and-proposal` adds an in-journey question, guidance retrieval and
  a new value proposal before continuing through postcode lookup.

The raw JSONL files are frozen observed runs. They are examples for understanding and
regression-testing the converter, not evaluation fixtures or an evaluation dataset.
The generated traces reference the named starting conversation fixture without
duplicating its messages; in-journey user messages remain events because they occurred
during the observed run.

Regenerate the committed common traces from the raw examples with:

```bash
uv run python -m agents.src.common_trace \
  agents/examples/common_trace/raw \
  --output-dir agents/examples/common_trace/expected \
  --overwrite
```

`agents/tests/test_common_trace_examples.py` checks that regeneration produces the
committed files exactly.
