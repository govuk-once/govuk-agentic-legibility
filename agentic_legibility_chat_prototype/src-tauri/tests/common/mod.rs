//! Shared harness for full-stack integration tests.
//!
//! Spawns the real `legibility-chat-mcp` sidecar (built and copied into
//! `src-tauri/binaries/` the way `dev.sh` does it — see `test-integration.sh`),
//! runs the FLEX API mock in-process, and drives conversations through the
//! real `#[tauri::command]` entry points (`send_message`, `submit_ui_input`)
//! against a `tauri::test` mock app. Only the FLEX REST API is mocked — LLM
//! calls go through the normal client code against whatever provider is
//! configured in the developer's real `~/.config/legibility-chat/config.json`.
//! Each test makes real, billed LLM calls, and fails fast if no `api_key` is
//! configured.

#![allow(dead_code)]

use std::path::PathBuf;
use std::sync::RwLock;
use std::time::Duration;

use tauri::Manager;

use legibility_chat_common::trace::{convert_to_yaml, Tracer};
use legibility_chat_lib::commands::chat::{send_message, submit_ui_input};
use legibility_chat_lib::config::AppConfig;
use legibility_chat_lib::llm::types::ChatMessage;
use legibility_chat_lib::mcp::McpClientEnum;
use legibility_chat_lib::state_machine::registry::{CardRegistry, StateRegistry, ToolRegistry};
use legibility_chat_lib::{build_router, seed_and_load_registries, ManagedState, PlaygroundDirs};

pub const FLEX_PORT: u16 = 8127;

pub fn repo_root() -> PathBuf {
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
pub fn compute_ui_answer(state: &ManagedState) -> String {
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

pub struct Harness {
    pub app: tauri::App<tauri::test::MockRuntime>,
    pub handle: tauri::AppHandle<tauri::test::MockRuntime>,
    #[allow(dead_code)]
    pub tmp: tempfile::TempDir,
    #[allow(dead_code)]
    pub live_resources_dir: PathBuf,
}

/// Builds the isolated app: real provider config, isolated `XDG_CONFIG_HOME`,
/// in-process FLEX mock, real sidecar spawn. `initial_state` optionally
/// overrides the state machine's starting state (default: alphabetically
/// first, which is "Advice") — useful for a test that wants to start already
/// inside `Execute` rather than relying on the LLM to navigate there itself.
pub async fn setup(initial_state: Option<&str>) -> Harness {
    // Real provider config, captured before XDG_CONFIG_HOME is redirected.
    let real_config = AppConfig::load();
    if real_config.provider.api_key.trim().is_empty() {
        panic!(
            "No LLM provider configured in ~/.config/legibility-chat/config.json. \
             This integration test makes real LLM calls through the normal client \
             code and needs a real provider.api_key set to run."
        );
    }

    // Isolate trace/registry files in a tempdir. The sidecar inherits this
    // env var too, so it writes to the same isolated location.
    let tmp = tempfile::tempdir().expect("create tempdir");
    unsafe {
        std::env::set_var("XDG_CONFIG_HOME", tmp.path());
    }

    // Start the FLEX mock in-process — this is what backs the four
    // address-lookup endpoints under live_resources/endpoints/*.md.
    std::thread::spawn(move || legibility_chat_mocks::flex::run(FLEX_PORT));
    wait_for_port(FLEX_PORT).await;

    // Build ManagedState directly, reusing the real provider config.
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

    // Real commands, real sidecar spawn — only the runtime's window/event
    // loop layer is mocked.
    let app = tauri::test::mock_builder()
        .plugin(tauri_plugin_shell::init())
        .manage(managed)
        .build(tauri::test::mock_context(tauri::test::noop_assets()))
        .expect("failed to build mock tauri app");

    let handle = app.handle().clone();

    // Seed registries, then optionally pin the starting state before
    // spawning the real legibility-chat-mcp sidecar.
    seed_and_load_registries(&handle);
    if let Some(name) = initial_state {
        *app.state::<ManagedState>().current_state.write().unwrap() = name.to_string();
    }

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

    Harness {
        app,
        handle,
        tmp,
        live_resources_dir,
    }
}

/// Sends `message` via the real `send_message` command, then polls and
/// answers any `ui_input` calls generically until it completes or `timeout`
/// elapses. Bounded so a model that never converges fails the test instead
/// of hanging it.
pub async fn drive(harness: &Harness, message: &str, timeout: Duration) {
    let send_handle = harness.handle.clone();
    let msg = message.to_string();
    let send_task = tokio::spawn(async move {
        let state = send_handle.state::<ManagedState>();
        send_message(msg, state, send_handle.clone()).await
    });

    let app = &harness.app;
    let handle = &harness.handle;
    let poll_result = tokio::time::timeout(timeout, async {
        let mut iterations = 0;
        loop {
            if send_task.is_finished() {
                break;
            }
            iterations += 1;
            assert!(
                iterations < 2000,
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
        "conversation did not finish within the timeout — the real LLM may be stuck in a ui_input loop",
    );

    let send_result = send_task.await.expect("send_message task panicked");
    send_result.expect("send_message returned an error");
}

/// No silent tool failures anywhere in the conversation (catches a confused
/// LLM as well as real router/dispatch errors).
pub fn assert_no_tool_failures(harness: &Harness) {
    let managed = harness.app.state::<ManagedState>();
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

/// Returns every tool call's name, in the order they appear in the
/// conversation (duplicates included) — the direct way to check which
/// tools the LLM actually invoked, e.g. whether `get_service` was called.
pub fn tool_call_names(harness: &Harness) -> Vec<String> {
    let managed = harness.app.state::<ManagedState>();
    let conv = managed.conversation.read().unwrap();
    conv.iter()
        .filter_map(|m: &ChatMessage| m.tool_calls.as_ref())
        .flatten()
        .map(|tc| tc.function.name.clone())
        .collect()
}

/// Returns every `fetch` tool call's `url` argument, in the order they
/// appear in the conversation — the most direct way to check which FLEX
/// endpoints were actually hit, independent of the (lossier) trace YAML.
pub fn fetch_urls(harness: &Harness) -> Vec<String> {
    let managed = harness.app.state::<ManagedState>();
    let conv = managed.conversation.read().unwrap();
    conv.iter()
        .filter_map(|m: &ChatMessage| m.tool_calls.as_ref())
        .flatten()
        .filter(|tc| tc.function.name == "fetch")
        .filter_map(|tc| {
            let args: serde_json::Value = serde_json::from_str(&tc.function.arguments).ok()?;
            args["url"].as_str().map(|s| s.to_string())
        })
        .collect()
}

/// Reads `run_id` from `trace.state.json` (written under the isolated
/// `XDG_CONFIG_HOME`), converts that run's slice of `trace.jsonl` to YAML,
/// and persists a copy to `tests/output/<name>` (outside the tempdir, which
/// is deleted on drop) so it's available for manual inspection after the
/// test run. Returns the raw YAML text and its parsed form.
pub fn convert_and_persist_trace(harness: &Harness, name: &str) -> (String, serde_yaml::Value) {
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

    let out_path = harness.tmp.path().join(name);
    convert_to_yaml(&run_id, "integration_test", &out_path).expect("convert_to_yaml failed");

    let persisted_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/output")
        .join(name);
    std::fs::create_dir_all(persisted_path.parent().unwrap()).expect("creating tests/output dir");
    std::fs::copy(&out_path, &persisted_path).expect("persisting trace YAML for inspection");

    let yaml_text = std::fs::read_to_string(&out_path).expect("reading converted YAML");
    let yaml: serde_yaml::Value = serde_yaml::from_str(&yaml_text).expect("parsing converted YAML");
    (yaml_text, yaml)
}

/// Shuts down the real sidecar explicitly. The flex-mock thread is
/// reclaimed when the test process exits.
pub async fn teardown(harness: Harness) {
    let managed = harness.app.state::<ManagedState>();
    let taken_router = managed.mcp_router.lock().await.take();
    if let Some(router) = taken_router {
        for server in router.into_servers() {
            let McpClientEnum::Stdio(client) = server.client;
            let _ = client.shutdown().await;
        }
    }
}
