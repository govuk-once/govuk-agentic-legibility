//! Standalone mock FLEX API server.
//!
//! Usage: flex-mock [port]  (default 8127)

fn main() {
    let port: u16 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(8127);
    legibility_chat_mocks::flex::run(port);
}
