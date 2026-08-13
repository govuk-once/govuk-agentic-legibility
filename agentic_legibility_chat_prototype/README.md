# Agentic Legibility Chat

A Tauri desktop app that runs a small LLM-driven state machine for guiding a caseworker or claimant through a UK government service journey. The LLM operates inside one of three states (**Advice → Plan → Execute**), each with its own system prompt and tool set defined in markdown files, and can render structured "cards" (service overviews, step checklists, progress summaries) in place of plain chat text.

## What this is

- A Rust/Tauri backend (`src-tauri`) that owns the state machine, talks to an OpenAI-compatible LLM API, and dispatches tool calls to a single bundled MCP (Model Context Protocol) sidecar process.
- A Svelte/Vite frontend (`ui`) that renders the chat window, state indicator, card bubbles, config panel, and first-run setup wizard.
- One bundled MCP sidecar binary, **`legibility-chat-mcp`** (`src-mcp` in this repo, stdio JSON-RPC), which always exposes `fetch`, `report_service_step`, and `ui_input` (the latter two are actually intercepted by the Tauri host before they'd reach this server). If the user configures a `live_resources_dir` (see below), it additionally exposes 12 read-only spec-lookup tools (`list_services`, `get_plan`, `search_specs`, etc.) plus `get_memory`/`add_memory` for persistent cross-session notes, all backed by that directory.

## Architecture

### The state machine

Three states, defined as markdown files with YAML frontmatter under `src-tauri/resources/defaults/states/`:

- **Advice** — general orientation, can transition to Plan or Execute
- **Plan** — lays out the steps of a service journey
- **Execute** — walks through a specific step

Each state file's frontmatter declares `valid_transitions` and the `tools` available in that state (tool names are looked up in the tool registry below; `change_state` is auto-injected into every state, see `state_machine/registry.rs`). The LLM calls `change_state` as a tool to move between states; `commands/chat.rs` intercepts that call on the host side rather than forwarding it to an MCP server.

### Tools

Markdown files under `src-tauri/resources/defaults/tools/state/`, one per tool, each with frontmatter (name, description, JSON schema) plus prose instructing the LLM on when/why to call it. Two categories:

- **Host-intercepted**: `change_state`, `ui_input`, `report_service_step` — handled directly by the Tauri backend for UI-side effects, never actually dispatched to an MCP server.
- **MCP-dispatched**: `fetch` — routed to `legibility-chat-mcp`'s real implementation (a `ureq`-based HTTP call). When a `live_resources_dir` is configured, `legibility-chat-mcp` additionally exposes 12 spec-lookup tools (`list_services`, `get_plan`, `search_specs`, etc.) plus `get_memory`/`add_memory`, supplied at runtime rather than from markdown — see `src-tauri/src/mcp/spec_tools.rs` and `src-mcp/src/tools/spec_tools.rs`.

### Cards

Markdown files under `src-tauri/resources/defaults/cards/`: `action_checklist` (ActionChecklist — a checklist of concrete next actions), `case_progress` (CaseProgress — a row of stage cards showing progress through a plan), and `key_facts` (KeyFacts — 3–5 key facts, figures, deadlines, or criteria as labelled rows). Each has frontmatter (`name`, `description`, `relevant_states`) and prose generation instructions. When `cards_enabled` is on, a card-selector LLM call picks a card by name/description, then a second LLM call renders the card's generation instructions into HTML, which `CardBubble.svelte` renders via `{@html}`. 

### Bundled resources and overrides

`src-tauri/resources/defaults/{states,tools/state,cards}/*.md` are compiled into the app bundle (see `tauri.conf.json`'s `bundle.resources`) and copied to `~/.config/legibility-chat/{states,tools,cards}/` on first run, or on "Reset to defaults" (`state_machine/loader.rs`). At runtime, `AppConfig.states_override_dir` / `tools_override_dir` / `cards_override_dir` can point the app at a different directory instead — useful for iterating on prompts without rebuilding.

### Config and first-run wizard

App config lives at `~/.config/legibility-chat/config.json` (`src-tauri/src/config.rs`), not environment variables — there's no `.env` file to set up. Key fields:

| Field | Purpose |
|---|---|
| `provider.{base_url,api_key,model}` | Main LLM provider — any OpenAI-compatible endpoint (OpenAI, Anthropic via the `/v1` shim, OpenRouter, etc.) |
| `analyser` | Optional cheaper/faster model override for the state-evaluation call; falls back to `provider` if unset |
| `states_override_dir` / `tools_override_dir` / `cards_override_dir` | Optional runtime overrides for the bundled markdown |
| `live_resources_dir` | Path to a directory with `endpoints/`, `services/`, `plans/` subdirs (and, once the LLM starts recording facts, a `memory.md` at its root). When set, `legibility-chat-mcp` is restarted with the directory wired in and its spec-lookup + memory tools become available; when unset, only the always-on tools (`fetch`, `change_state`, `ui_input`, `report_service_step`) run |
| `cards_enabled` | Whether the card-selector pipeline runs at all (default on) |

`SetupWizard.svelte` drives first-run configuration of these fields through `commands/wizard.rs`.

## Prerequisites

- [Rust](https://www.rust-lang.org/tools/install) (stable toolchain)
- [Node.js](https://nodejs.org/) 18+ and [pnpm](https://pnpm.io/)
- Tauri's native dependencies for your OS (e.g. WebKit2GTK on Linux — see the [Tauri prerequisites guide](https://v2.tauri.app/start/prerequisites/))
- Tauri CLI must be installed globally so `dev.sh` can run it as a `tauri` command on your PATH. 

## Building the sidecar

Before the first run, create the folder the sidecar binary is copied into:

    mkdir -p src-tauri/binaries

This folder is gitignored, so a fresh clone never has it, and `dev.sh` does
not create it. Without it, `dev.sh` fails at the end with:

    cp: src-tauri/binaries/legibility-chat-mcp-<target-triple>: No such file or directory


## Local development

```bash
pnpm install --dir ui
./dev.sh
```

`dev.sh` builds the `legibility-chat-mcp` sidecar binary, copies it into `src-tauri/binaries/`, frees port 5173, and launches `tauri dev`.

## Mock server

`src-mocks` (a Rust crate, `legibility-chat-mocks`) stands in for the real upstream government APIs referenced by `endpoint:` URLs in a `live_resources_dir/endpoints/*.md` spec directory — so you can exercise the `fetch` tool and full Advice → Plan → Execute flow without live credentials or network access to the real services. It's also used in-process by the `trace_conversation` integration test (see Validation).

Run it standalone:

```bash
cargo run -p legibility-chat-mocks --bin flex-mock -- [port]   # default port 8127
```

Or launch it alongside the app in one step:

```bash
./dev-with-mock.sh
```

This builds and starts the mock in the background, runs `./dev.sh` in the foreground, and stops the mock when `dev.sh` exits (Ctrl-C, crash, or normal exit). Override the port with `MOCK_PORT=9000 ./dev-with-mock.sh`.

It covers five path prefixes matching the FLEX API domains used in the bundled specs — `/udp` (One Login User Data Platform), `/dvla` (DVLA driver/vehicle/share-code APIs), `/uns` (Unified Notification Service), `/local-council` (MHCLG local authority lookup), and `/example` (a generic example domain for todos/resources/headers), plus the address-lookup routes (`/choose-address-entry-method`, `/find-address-by-postcode`, `/enter-address-manually`, `/confirm-new-address`). Each route is a `Route { method, pattern: Regex, status, handler }` entry in `src-mocks/src/flex.rs`'s route table; more specific paths must be listed before overlapping general ones, since the first regex match wins.

The mock only returns canned data for routes it already knows about — it does **not** read the `live_resources_dir/endpoints/*.md` files at runtime. To keep it in sync with the "expected" service endpoints declared there:

1. For each `.md` file under your `live_resources_dir/endpoints/`, note its frontmatter `method` and `endpoint` (a full URL, e.g. `https://flex.account.gov.uk/dvla/v1/driving-licence`).
2. In `src-mocks/src/flex.rs`, add or update a route entry with the same `method` and a `pattern` regex matching the URL's path (everything after the host) under the matching prefix section (`/udp`, `/dvla`, `/uns`, `/local-council`, `/example`), with a `handler` returning representative JSON for that response shape.
3. Point the app's `fetch` calls at the mock instead of the real host by changing the affected endpoint spec's `endpoint:` frontmatter from `https://flex.account.gov.uk/...` to `http://localhost:8127/...` (or your chosen `[port]`) in your local `live_resources_dir` copy — `fetch` uses that URL verbatim, there's no built-in host rewriting.
4. If you remove or rename an endpoint spec, remove or update the corresponding route entry so the mock doesn't drift from what the specs actually describe.

## Validation

```bash
cargo build --workspace          # both Rust crates: legibility-chat, legibility-chat-mcp
cargo test --workspace           # unit tests + doctests
pnpm --dir ui check              # svelte-check + tsc, no separate lint/test scripts exist yet
```

There is no `pnpm lint`, `pnpm test`, or browser test suite configured for `ui/` at present — `check` (type-checking only) is the only frontend validation gate.

### Integration tests

`src-tauri/tests/` has full-stack integration tests that spawn the real `legibility-chat-mcp` sidecar, run the mock FLEX API (`legibility-chat-mocks`) in-process, and drive the actual `send_message`/`submit_ui_input` Tauri commands — **against your real, configured LLM provider**. Only the FLEX REST API is mocked; the LLM calls are genuine, unscripted, and billed to whatever provider is set in `~/.config/legibility-chat/config.json`.

Because of this, each test run:

- **Requires a real provider configured** (`provider.{base_url,api_key,model}` in your config) — a test fails fast with a clear message if none is set.
- **Costs real API usage** — the LLM is not mocked, so every run makes genuine, billed calls.
- **Is not fully deterministic** — the LLM's exact tool-call sequence and phrasing can vary between runs. Tests assert on outcomes (which endpoints got hit, that no tool call failed, that certain trace events occurred) rather than an exact scripted transcript.
- **Needs the sidecar binary built and copied into `src-tauri/binaries/`** first, the same way `dev.sh` does it — either run `./test-integration.sh` (below), or do it manually:

  ```bash
  TARGET=$(rustc -vV | grep host | cut -d' ' -f2)
  cargo build -p legibility-chat-mcp
  cp target/debug/legibility-chat-mcp "src-tauri/binaries/legibility-chat-mcp-${TARGET}"
  ```

Each test isolates its own `config.json`/`trace.jsonl`/`trace.state.json` in a fresh tempdir (via `XDG_CONFIG_HOME`) — it won't touch your real trace history — but it does read your real `config.json` once up front to capture provider credentials before overriding the location.

Run the primary end-to-end conversation test via the helper script, which also takes care of the sidecar build step:

```bash
./test-integration.sh
```

Run an individual test binary directly with `cargo test` (add `-- --nocapture` to see `println!` output, e.g. the ordered list of tool calls):

```bash
cargo test -p legibility-chat --test trace_conversation -- --nocapture
cargo test -p legibility-chat --test change_driving_licence_address_postcode -- --nocapture
cargo test -p legibility-chat --test change_driving_licence_address_manual -- --nocapture
cargo test -p legibility-chat --test change_driving_licence_address_llm_choice -- --nocapture
```

What each covers:

| Test | Scenario |
|---|---|
| `trace_conversation` | General open-ended conversation starting in the `Advice` state, asserting only that a `user_message` trace event is recorded (loosest test — the LLM's path through Advice/Plan/Execute isn't pinned) |
| `change_driving_licence_address_postcode` | Drives the `change_driving_licence_address` service starting in `Execute`, steered toward the postcode-lookup path; asserts `get_service` was called and the postcode/confirm endpoints were hit |
| `change_driving_licence_address_manual` | Same service, steered toward manual address entry instead |
| `change_driving_licence_address_llm_choice` | Same service, but the prompt offers both postcode and manual-entry facts and lets the real LLM pick a path itself. This one is the most exposed to real-LLM non-determinism — it can fail if the model tries a path, changes its mind, or ends the conversation before confirming |

Each test converts its trace to YAML and writes a copy under `src-tauri/tests/output/*.yaml` (gitignored) for inspection after the run.

Test harness code shared across these files lives in `src-tauri/tests/common/mod.rs` (not a test itself — Cargo treats a `tests/common/` module specially and doesn't compile it as its own binary).

## Production build

```bash
./dev.sh   # or the manual sidecar-build steps above
cd src-tauri && cargo tauri build
```

Bundled artifacts land in `src-tauri/target/release/bundle/` (`.AppImage`/`.deb` on Linux, `.dmg`/`.app` on macOS, NSIS `.exe` on Windows — signing/notarization not configured here).

## Project structure

```
src-tauri/
  src/
    commands/          Tauri command handlers (chat, config, state, wizard, files, live_resources)
    state_machine/      loader (markdown parsing, seeding, reset), registry, types
    mcp/                 router, legibility_chat_client (legibility-chat-mcp), spec_tools (gated tool-name list)
    llm/                 provider-agnostic client, OpenAI + Anthropic SSE parsing, shared types
  resources/defaults/     bundled states/tools/cards markdown (see Architecture above)
src-mcp/                 legibility-chat-mcp sidecar: fetch/report_service_step/ui_input plus,
                          when live_resources_dir is set, spec-lookup + memory tools (context.rs, specs/, tools/spec_tools.rs)
ui/
  src/lib/                Svelte components (ChatWindow, CardBubble, StateSelector, SetupWizard, PlaygroundPanel, ...)
src-mocks/               legibility-chat-mocks: FLEX API mock (see Mock server above), also used in-process by tests
dev-with-mock.sh          runs the flex-mock binary alongside dev.sh
.claude/plans/            design docs for completed and in-flight features
```

## Maintenance notes and known constraints

- Card CSS classes are not self-contained — they assume a stylesheet from `../../service_creator/src/app.css` (also a sibling project) is present at runtime. There is no local fallback stylesheet in this repo.
- `relevant_states` in card frontmatter is parsed but not currently used to gate which cards are eligible in which state — it's descriptive metadata only.

## Follow-up work

- No frontend lint or automated test suite exists (`ui/package.json` only has `check`); consider adding one before the component count grows further.

### Authors and Support
This project was made by Alex and Jen at Considerate Digital. If you need support please [contact us](https://considerate.digital).
