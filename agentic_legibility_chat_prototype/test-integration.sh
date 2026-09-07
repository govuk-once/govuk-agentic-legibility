#!/usr/bin/env bash
set -e

TARGET=$(rustc -vV | grep host | cut -d' ' -f2)

echo "Building legibility-chat-mcp sidecar..."
cargo build -p legibility-chat-mcp
cp "target/debug/legibility-chat-mcp" "src-tauri/binaries/legibility-chat-mcp-${TARGET}"
echo "Sidecar copied to src-tauri/binaries/legibility-chat-mcp-${TARGET}"

echo "Running trace_conversation integration test (real LLM calls, mocked FLEX API)..."
cargo test -p legibility-chat --test trace_conversation -- --nocapture
