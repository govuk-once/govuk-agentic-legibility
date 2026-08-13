
use crate::context::AppContext;
use legibility_chat_common::trace::TraceEvent;

pub fn rand_u32() -> u32 {
    // Simple deterministic stub — not cryptographically random
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_nanos())
        .unwrap_or(0)
}

pub async fn fetch(ctx: &AppContext, args: &serde_json::Value) -> String {
    let url = match args["url"].as_str() {
        Some(u) => u,
        None => return "[fetch error] missing required 'url' argument".to_string(),
    };
    let method = args["method"].as_str().unwrap_or("GET").to_uppercase();
    let interaction_id = args["interaction_id"].as_str();

    // Add trace logging before request is made
    if let Some(body_str) = args["body"].as_str() {
        if let Ok(body_values) = serde_json::from_str(body_str) {
            let mut tracer = ctx.tracer.write().await;
            tracer.add_event(
                TraceEvent::ValuesProposed,
                interaction_id,
                &url,
                body_values
            );
        }
    }

    let mut request = ureq::request(&method, url);

    if let Some(headers_str) = args["headers"].as_str() {
        if let Ok(headers_obj) = serde_json::from_str::<serde_json::Map<String, serde_json::Value>>(headers_str) {
            for (key, val) in &headers_obj {
                if let Some(v) = val.as_str() {
                    request = request.set(key, v);
                }
            }
        }
    }

    let body_str = args["body"].as_str().unwrap_or("");

    let response = if body_str.is_empty() {
        request.call()
    } else {
        request.send_string(body_str)
    };

    match response {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.into_string().unwrap_or_else(|e| format!("[body read error: {}]", e));
            let truncated = if body.len() > 4000 {
                format!("{}\n... [truncated {} bytes]", &body[..4000], body.len() - 4000)
            } else {
                body
            };

            // If trucated body can be parsed to JSON, values are extracted dynamically into 
            // HashMap
            if let Ok(body_values) = serde_json::from_str(&truncated) {
                // Add trace logging
                let mut tracer = ctx.tracer.write().await;
                tracer.add_event(
                    TraceEvent::ValuesSubmitted,
                    interaction_id,
                    &url,
                    body_values
                );
    

            }
            
            
             

            format!("HTTP {}\n{}", status, truncated)
        }
        Err(e) => format!("[fetch error] {}", e),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Regression test for a bug where `args["body"]` (a `serde_json::Value`
    /// string) was fed straight into `.to_string()` before parsing, which
    /// re-serializes it with an extra layer of quoting/escaping — so a
    /// well-formed JSON body always failed to parse and `ValuesProposed` was
    /// silently never logged. Uses an unreachable URL so the test doesn't
    /// depend on network access: the trace write happens before the request
    /// is made, so the request's own (expected) failure doesn't matter here.
    #[tokio::test]
    async fn fetch_logs_values_proposed_for_a_json_body() {
        static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
        let _guard = ENV_LOCK.lock().unwrap();

        let tmp = tempfile::tempdir().unwrap();
        std::env::set_var("XDG_CONFIG_HOME", tmp.path());

        let ctx = AppContext::disabled_for_test();
        let args = serde_json::json!({
            "url": "http://127.0.0.1:1",
            "method": "POST",
            "body": "{\"postcode\":\"SW1A 1AA\"}",
        });
        fetch(&ctx, &args).await;

        let trace_path = tmp.path().join("legibility-chat").join("trace.jsonl");
        let contents = std::fs::read_to_string(&trace_path)
            .unwrap_or_else(|e| panic!("no trace.jsonl written: {e}"));

        std::env::remove_var("XDG_CONFIG_HOME");

        assert!(
            contents.contains("\"type\":\"ValuesProposed\""),
            "expected a ValuesProposed trace line, got:\n{contents}"
        );
    }
}

