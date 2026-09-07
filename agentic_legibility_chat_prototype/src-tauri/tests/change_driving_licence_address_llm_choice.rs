//! Full-stack integration test: drives the `change_driving_licence_address`
//! service (`live_resources/services/change_driving_licence_address.md`)
//! end-to-end, letting the real, unscripted LLM pick **either** the
//! postcode-lookup or manual-entry path itself (both facts are offered in
//! the initial message; the LLM decides which endpoint to call), against
//! the mocked FLEX API. See `tests/common/mod.rs` for what's real vs
//! mocked, and `change_driving_licence_address_postcode.rs` /
//! `change_driving_licence_address_manual.rs` for the two variants that
//! pin a specific path.

mod common;

use std::time::Duration;

#[tokio::test]
async fn drives_change_driving_licence_address_service_llm_chooses_entry_method() {
    let harness = common::setup(Some("Execute")).await;

    common::drive(
        &harness,
        "Please execute the 'change_driving_licence_address' service for me. \
         Look up the service and its endpoints first, then walk through each \
         required step, choosing whichever address entry method you think is \
         most appropriate — postcode lookup or manual entry. If you use \
         postcode lookup, my postcode is SW1A 1AA. If you'd rather enter it \
         manually, my new address is 42 Baker Street, Marylebone, London, \
         NW1 6XE. Ask me to confirm before finalising, and tell me at the \
         end whether my address was updated successfully.",
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
    let used_postcode = hit("find-address-by-postcode");
    let used_manual = hit("enter-address-manually");

    assert!(
        hit("choose-address-entry-method"),
        "expected a fetch call to choose-address-entry-method (required step 1). \
         fetch calls made: {urls:?}"
    );
    assert!(
        used_postcode || used_manual,
        "expected a fetch call to either find-address-by-postcode or \
         enter-address-manually (the LLM's choice) — got neither. \
         fetch calls made: {urls:?}"
    );
    assert!(
        hit("confirm-new-address"),
        "expected a fetch call to confirm-new-address (required step 4). \
         fetch calls made: {urls:?}"
    );

    println!(
        "LLM chose: {}",
        match (used_postcode, used_manual) {
            (true, false) => "postcode lookup",
            (false, true) => "manual entry",
            (true, true) => "both (unexpected, but not disallowed)",
            (false, false) => unreachable!("caught by the assertion above"),
        }
    );

    let (yaml_text, yaml) = common::convert_and_persist_trace(
        &harness,
        "change_driving_licence_address_llm_choice.yaml",
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
