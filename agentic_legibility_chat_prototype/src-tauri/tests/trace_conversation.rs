//! Full-stack integration test.
//!
//! Spawns the real `legibility-chat-mcp` sidecar (built and copied into
//! `src-tauri/binaries/` the way `dev.sh` does it — see `test-integration.sh`),
//! runs the FLEX API mock in-process, and drives a conversation through the
//! real `#[tauri::command]` entry points (`send_message`, `submit_ui_input`)
//! against a `tauri::test` mock app. Only the FLEX REST API is mocked — LLM
//! calls go through the normal client code against whatever provider is
//! configured in the developer's real `~/.config/legibility-chat/config.json`.
//! Each run makes real, billed LLM calls, and fails fast if no `api_key` is
//! configured.

use std::path::PathBuf;
use std::sync::RwLock;
use std::time::Duration;

use tauri::Manager;

use legibility_chat_common::trace::{convert_to_yaml, Tracer};
use legibility_chat_lib::commands::chat::{send_message, submit_ui_input};
use legibility_chat_lib::config::AppConfig;
use legibility_chat_lib::mcp::McpClientEnum;
use legibility_chat_lib::state_machine::registry::{CardRegistry, StateRegistry, ToolRegistry};
use legibility_chat_lib::{build_router, seed_and_load_registries, ManagedState, PlaygroundDirs};

const FLEX_PORT: u16 = 8127;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("src-tauri has a parent dir")
        .to_path_buf()
}

async fn wait_for_port(port: u16) {
    for _ in 0..100 {
        if tokio::net::TcpStream::connect(("127.0.0.1", port))
            .await
            .is_ok()
        {
            return;
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    panic!("flex-mock did not start listening on port {port}");
}

/// Picks a plausible answer for the latest `ui_input` tool call so the real
/// (unscripted) LLM's conversation can proceed without a fixed turn-by-turn
/// script.
fn compute_ui_answer(state: &ManagedState) -> String {
    let args: Option<serde_json::Value> = {
        let conv = state.conversation.read().unwrap();
        conv.iter()
            .rev()
            .find_map(|m| {
                m.tool_calls
                    .as_ref()
                    .and_then(|tcs| tcs.iter().find(|tc| tc.function.name == "ui_input"))
            })
            .map(|tc| serde_json::from_str(&tc.function.arguments).unwrap_or_default())
    };

    let Some(args) = args else {
        return "yes".to_string();
    };

    if let Some(options) = args["options"].as_array() {
        let opts: Vec<&str> = options.iter().filter_map(|v| v.as_str()).collect();
        if let Some(postcode_opt) = opts.iter().find(|o| o.to_lowercase().contains("postcode")) {
            return postcode_opt.to_string();
        }
        if let Some(first) = opts.first() {
            return first.to_string();
        }
    }

    let name = args["name"].as_str().unwrap_or("").to_lowercase();
    let description = args["description"].as_str().unwrap_or("").to_lowercase();
    let input_type = args["input_type"].as_str().unwrap_or("text");

    if name.contains("postcode") || description.contains("postcode") {
        "SW1A 1AA".to_string()
    } else if input_type == "confirm" || name.contains("confirm") || description.contains("confirm") {
        "yes".to_string()
    } else {
        "SW1A 1AA".to_string()
    }
}

#[tokio::test]
async fn drives_conversation_and_converts_trace_to_yaml() {
    // 1. Real provider config, captured before XDG_CONFIG_HOME is redirected.
    let real_config = AppConfig::load();
    if real_config.provider.api_key.trim().is_empty() {
        panic!(
            "No LLM provider configured in ~/.config/legibility-chat/config.json. \
             This integration test makes real LLM calls through the normal client \
             code and needs a real provider.api_key set to run."
        );
    }

    // 2. Isolate trace/registry files in a tempdir. The sidecar inherits this
    // env var too, so it writes to the same isolated location.
    let tmp = tempfile::tempdir().expect("create tempdir");
    unsafe {
        std::env::set_var("XDG_CONFIG_HOME", tmp.path());
    }

    // 3. Start the FLEX mock in-process — this is what backs the four
    // address-lookup endpoints under live_resources/endpoints/*.md.
    std::thread::spawn(move || legibility_chat_mocks::flex::run(FLEX_PORT));
    wait_for_port(FLEX_PORT).await;

    // 4. Build ManagedState directly, reusing the real provider config.
    let live_resources_dir = repo_root().join("live_resources");
    let mut config = real_config;
    config.live_resources_dir = Some(live_resources_dir.to_string_lossy().to_string());
    config.cards_enabled = false;

    let managed = ManagedState {
        current_state: RwLock::new(String::new()),
        state_registry: RwLock::new(StateRegistry::empty()),
        tool_registry: RwLock::new(ToolRegistry::empty()),
        card_registry: RwLock::new(CardRegistry::empty()),
        config: RwLock::new(config),
        conversation: RwLock::new(Vec::new()),
        mcp_router: tokio::sync::Mutex::new(None),
        pending_ui_input: tokio::sync::Mutex::new(None),
        playground_dirs: RwLock::new(PlaygroundDirs {
            states: tmp.path().join("states"),
            tools: tmp.path().join("tools"),
            cards: tmp.path().join("cards"),
        }),
        tracer: RwLock::new(Tracer::new()),
    };

    // 5. Real commands, real sidecar spawn — only the runtime's window/event
    // loop layer is mocked.
    let app = tauri::test::mock_builder()
        .plugin(tauri_plugin_shell::init())
        .manage(managed)
        .build(tauri::test::mock_context(tauri::test::noop_assets()))
        .expect("failed to build mock tauri app");

    let handle = app.handle().clone();

    // 6. Seed registries, then spawn the real legibility-chat-mcp sidecar.
    seed_and_load_registries(&handle);

    let state_tools = {
        let state = app.state::<ManagedState>();
        let reg = state.tool_registry.read().unwrap();
        let bare: Vec<String> = reg
            .state_owned_tools()
            .into_iter()
            .map(|s| s.to_string())
            .collect();
        reg.to_llm_tools(&bare)
    };

    let router = build_router(
        Some(&live_resources_dir.to_string_lossy()),
        Some(&handle),
        state_tools,
        None,
    )
    .await
    .expect("build_router failed to spawn the legibility-chat-mcp sidecar");
    *app.state::<ManagedState>().mcp_router.lock().await = Some(router);

    // 7. Drive the conversation via the real send_message command.
    let send_handle = handle.clone();
    let send_task = tokio::spawn(async move {
        let state = send_handle.state::<ManagedState>();
        send_message(
            "I need to update the address on my driving licence.".to_string(),
            state,
            send_handle.clone(),
        )
        .await
    });

    // 8. Answer whatever ui_input calls come back, generically — the LLM
    // isn't scripted, so we can't assume an exact turn order. Bounded so a
    // model that never converges fails the test instead of hanging it.
    let poll_result = tokio::time::timeout(Duration::from_secs(180), async {
        let mut iterations = 0;
        loop {
            if send_task.is_finished() {
                break;
            }
            iterations += 1;
            assert!(
                iterations < 400,
                "too many ui_input polling iterations without send_message finishing"
            );

            let has_pending = app
                .state::<ManagedState>()
                .pending_ui_input
                .lock()
                .await
                .is_some();
            if has_pending {
                let answer = compute_ui_answer(&app.state::<ManagedState>());
                let sub_state = handle.state::<ManagedState>();
                submit_ui_input(answer, sub_state)
                    .await
                    .expect("submit_ui_input failed");
            }

            tokio::time::sleep(Duration::from_millis(150)).await;
        }
    })
    .await;

    poll_result.expect(
        "conversation did not finish within 180s — the real LLM may be stuck in a ui_input loop",
    );

    // 9. Await the spawned task and assert it finished cleanly.
    let send_result = send_task.await.expect("send_message task panicked");
    send_result.expect("send_message returned an error");

    // No silent tool failures anywhere in the conversation (catches a
    // confused LLM as well as real router/dispatch errors).
    {
        let managed = app.state::<ManagedState>();
        let conv = managed.conversation.read().unwrap();
        for msg in conv.iter() {
            if let Some(content) = &msg.content {
                assert!(
                    !content.contains("Tool error:") && !content.contains("[fetch error]"),
                    "conversation contains a tool failure: {content}"
                );
            }
        }
    }

    // 10. Read run_id from trace.state.json (written under the isolated
    // XDG_CONFIG_HOME) and convert the run's slice of trace.jsonl to YAML.
    let trace_state_path = dirs::config_dir()
        .expect("config dir")
        .join("legibility-chat")
        .join("trace.state.json");
    let trace_state: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(&trace_state_path)
            .unwrap_or_else(|e| panic!("reading {trace_state_path:?}: {e}")),
    )
    .expect("parsing trace.state.json");
    let run_id = trace_state["run_id"]
        .as_str()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| {
            panic!("no run_id recorded in {trace_state_path:?} — no trace events were emitted")
        })
        .to_string();

    let out_path = tmp.path().join("trace_output.yaml");
    convert_to_yaml(&run_id, "integration_test", &out_path).expect("convert_to_yaml failed");

    // Persist a copy outside the tempdir (which is deleted on drop) so the
    // converted YAML is available for manual inspection after the test run.
    let persisted_path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/output/trace_output.yaml");
    std::fs::create_dir_all(persisted_path.parent().unwrap())
        .expect("creating tests/output dir");
    std::fs::copy(&out_path, &persisted_path).expect("persisting trace YAML for inspection");

    // 11. Assert on shape that doesn't depend on exact turn order. The LLM is
    // real and unscripted, so a single initial message is not guaranteed to
    // reach ui_input/fetch in one turn — observed live runs range from
    // "replies with plain text, no tools" to "retrieves guidance for several
    // endpoints, then replies with text" to a full ui_input/fetch round-trip.
    // We only assert on what every successful run must contain: the user's
    // message made it into the trace, the run converts to valid YAML, and no
    // tool call anywhere in the conversation silently failed.
    let yaml_text = std::fs::read_to_string(&out_path).expect("reading converted YAML");
    let yaml: serde_yaml::Value = serde_yaml::from_str(&yaml_text).expect("parsing converted YAML");

    let events = yaml["events"]
        .as_sequence()
        .unwrap_or_else(|| panic!("no events in trace YAML:\n{yaml_text}"));
    let has_event = |ty: &str| events.iter().any(|e| e["type"].as_str() == Some(ty));

    assert!(
        has_event("user_message"),
        "expected a user_message event. YAML written to {out_path:?}:\n{yaml_text}"
    );

    // 12. Teardown: shut down the sidecar explicitly. The flex-mock thread
    // is reclaimed when the test process exits.
    let managed = app.state::<ManagedState>();
    let taken_router = managed.mcp_router.lock().await.take();
    if let Some(router) = taken_router {
        for server in router.into_servers() {
            let McpClientEnum::Stdio(client) = server.client;
            let _ = client.shutdown().await;
        }
    }
}
