//! Full-stack integration test: drives the `change_driving_licence_address`
//! service (`live_resources/services/change_driving_licence_address.md`)
//! end-to-end through the **postcode-lookup** path —
//! `choose_address_entry_method` -> `find_address_by_postcode` ->
//! `confirm_new_address` — against the real, unscripted LLM and the mocked
//! FLEX API. See `tests/common/mod.rs` for what's real vs mocked.
//!
//! Companion variants: `change_driving_licence_address_manual.rs` (steers
//! toward manual entry instead) and `change_driving_licence_address_llm_choice.rs`
//! (lets the LLM pick either path itself).
//!
//! The conversation starts already inside the `Execute` state (rather than
//! `Advice`) and the initial message names the service and postcode
//! explicitly, so the real LLM doesn't have to independently discover which
//! service applies or which entry path to take — it still has to look up
//! the service/endpoint specs and make the real `fetch` calls itself.

mod common;

use std::time::Duration;

#[tokio::test]
async fn drives_change_driving_licence_address_service_via_postcode_lookup() {
    let harness = common::setup(Some("Execute")).await;

    common::drive(
        &harness,
        "Please execute the 'change_driving_licence_address' service for me. \
         Look up the service and its endpoints first, then walk through each \
         required step. I want to find my new address using the postcode \
         lookup method, not manual entry — my postcode is SW1A 1AA. Ask me \
         to confirm before finalising, and tell me at the end whether my \
         address was updated successfully.",
        Duration::from_secs(240),
    )
    .await;

    common::assert_no_tool_failures(&harness);

    let tool_names = common::tool_call_names(&harness);
    println!("tools called (in order): {tool_names:?}");
    assert!(
        tool_names.iter().any(|n| n == "get_service"),
        "expected the LLM to call get_service at some point. tools called: {tool_names:?}"
    );

    let urls = common::fetch_urls(&harness);
    let hit = |path: &str| urls.iter().any(|u| u.contains(path));

    assert!(
        hit("choose-address-entry-method"),
        "expected a fetch call to choose-address-entry-method (required step 1). \
         fetch calls made: {urls:?}"
    );
    assert!(
        hit("find-address-by-postcode"),
        "expected a fetch call to find-address-by-postcode — the prompt explicitly \
         asked for the postcode-lookup path. fetch calls made: {urls:?}"
    );
    assert!(
        hit("confirm-new-address"),
        "expected a fetch call to confirm-new-address (required step 4). \
         fetch calls made: {urls:?}"
    );

    let (yaml_text, yaml) = common::convert_and_persist_trace(
        &harness,
        "change_driving_licence_address_postcode.yaml",
    );
    let events = yaml["events"]
        .as_sequence()
        .unwrap_or_else(|| panic!("no events in trace YAML:\n{yaml_text}"));
    let has_event = |ty: &str| events.iter().any(|e| e["type"].as_str() == Some(ty));

    assert!(
        has_event("values_submitted"),
        "expected at least one values_submitted event (a real fetch response recorded \
         through the mock FLEX API). YAML:\n{yaml_text}"
    );

    common::teardown(harness).await;
}
