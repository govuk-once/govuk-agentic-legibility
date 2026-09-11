# Captured executor checkpoints

This directory contains semantic `InterpreterState` snapshots captured from deliberately synthetic journeys for evaluation.

Capture a workflow while it is paused at the target input with `python -m evaluation.capture_checkpoint`. Do not commit checkpoints captured from real users: frame variables and transcripts can contain personal data collected earlier in the journey.

A targeted scenario can reference a captured checkpoint by ID:

```yaml
checkpoint:
  id: "ma-date-stopped-work"
  process_id: "section4_about_payment"
  state_id: "prompt_date_stopped_work"
```

`checkpoint_runner.py` resolves the ID to `<id>.json` in this directory and starts each evaluation repetition from a fresh `InterpreterState` built from the captured stack frames, variables, transcript, step counter and environment. `invoker_state_id` values are rehydrated from the workflow definition so nested subprocesses return to their parent frames normally.

A checkpoint is captured while an `InputState` is already suspended at step `N`. A new Temporal workflow must execute that input state again, so the loader starts from step counter `N - 1`; the interpreter then recreates step `N` and issues a fresh input token. The captured `awaiting` object is therefore validation metadata, not runtime state to restore.
