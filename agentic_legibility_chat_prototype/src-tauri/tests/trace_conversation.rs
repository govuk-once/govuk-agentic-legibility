//! Full-stack integration test: a general, open-ended conversation.
//!
//! See `tests/common/mod.rs` for what's real vs mocked. This test doesn't
//! steer the LLM toward any particular service — it only exercises the
//! plumbing (real sidecar, real mock FLEX API, real LLM, trace-to-YAML
//! conversion) and checks nothing silently failed. For a test that drives a
//! specific service end-to-end, see `change_driving_licence_address.rs`.

mod common;

use std::time::Duration;

#[tokio::test]
async fn drives_conversation_and_converts_trace_to_yaml() {
    let harness = common::setup(None).await;

    common::drive(
        &harness,
        "I need to update the address on my driving licence.",
        Duration::from_secs(180),
    )
    .await;

    common::assert_no_tool_failures(&harness);

    // The LLM is real and unscripted, so a single initial message is not
    // guaranteed to reach ui_input/fetch in one turn — observed live runs
    // range from "replies with plain text, no tools" to "retrieves guidance
    // for several endpoints, then replies with text" to a full
    // ui_input/fetch round-trip. We only assert on what every successful run
    // must contain: the user's message made it into the trace, and the run
    // converts to valid YAML.
    let (yaml_text, yaml) = common::convert_and_persist_trace(&harness, "trace_output.yaml");
    let events = yaml["events"]
        .as_sequence()
        .unwrap_or_else(|| panic!("no events in trace YAML:\n{yaml_text}"));
    let has_event = |ty: &str| events.iter().any(|e| e["type"].as_str() == Some(ty));

    assert!(
        has_event("user_message"),
        "expected a user_message event. YAML:\n{yaml_text}"
    );

    common::teardown(harness).await;
}
