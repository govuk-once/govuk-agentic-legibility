use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    error::Error,
    fs,
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    time::{SystemTime, UNIX_EPOCH},
};
use uuid::Uuid;

use fs4::FileExt;

use strum::{Display, AsRefStr};

use dirs;

#[derive(Display, AsRefStr)]
pub enum TraceEvent {
    InteractionAvailable,
    ValuesProposed,
    UserMessage,
    AnswerPresented,
    GuidanceRetrieved,
    ValuesSubmitted,
    JourneyFinished
}

/// Shared state for one trace session (`run_id`/`journey_id`/`sequence_no`),
/// persisted at `state_path()` and coordinated across processes with an
/// exclusive file lock. `src-mcp` and `src-tauri` each hold their own
/// in-process `Tracer` handle, but every call reads and rewrites this file
/// under lock, so both processes converge on one run, one journey, and one
/// monotonically increasing sequence.
#[derive(Serialize, Deserialize, Default)]
struct TraceState {
    #[serde(default)]
    run_id: String,
    #[serde(default)]
    journey_id: String,
    #[serde(default)]
    sequence_no: u32,
}

pub struct Tracer {
    version: String,
}

impl Tracer {
    pub fn new() -> Tracer {
        Self {
            version: String::from("0.1"),
        }
    }

    pub fn set_journey(&mut self, journey: &str) -> io::Result<()> {
        with_locked_state(|state| {
            if state.run_id.is_empty() {
                state.run_id = Uuid::new_v4().to_string();
            }
            if state.journey_id != String::from(journey) {
                state.journey_id = String::from(journey);
                state.sequence_no = 0;
            }
            Ok(())
        })
    }

    pub fn start_trace(&mut self) -> io::Result<()> {
        with_locked_state(|state| {
            if state.run_id.is_empty() {
                state.run_id = Uuid::new_v4().to_string();
            }

            let mut trace_file = fs::OpenOptions::new()
                .create(true)
                .write(true)
                .append(true)
                .open(&config_path())?;

            writeln!(trace_file, "{}",
                json!({
                    "run_id": &state.run_id,
                    "sequence": state.sequence_no,
                    "timestamp": SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs(),
                    "trace_version": &self.version,
                    "journey_id": &state.journey_id,
                    "consumer": "agent_assisted_chat",
                })
            )?;

            state.sequence_no += 1;

            Ok(())
        })
    }

    pub fn add_event(&mut self, event_type: TraceEvent, interaction_id: Option<&str>, content: &str, values: HashMap<String, Value>) -> Result<(), Box<dyn Error>> {
        with_locked_state(|state| {
            if state.run_id.is_empty() {
                state.run_id = Uuid::new_v4().to_string();
            }

            let mut trace_file = fs::OpenOptions::new()
                .create(true)
                .write(true)
                .append(true)
                .open(&config_path())?;

            writeln!(trace_file, "{}",
                json!({
                    "run_id": &state.run_id,
                    "sequence": state.sequence_no,
                    "timestamp": SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs(),
                    "journey_id": &state.journey_id,
                    "type": event_type.as_ref(),
                    "interaction_id": &interaction_id,
                    // chat content from user (UserMessage only)
                    "content": &content,
                    // request values if tool is called
                    "values": &values
                })
            )?;

            state.sequence_no += 1;

            Ok(())
        })?;

        Ok(())
    }

    /// `GuidanceRetrieved` doesn't fit the generic `content`/`values` shape —
    /// it carries a structured `source` reference to the spec doc that was
    /// looked up, so it gets its own method rather than overloading `values`
    /// by convention.
    pub fn add_guidance_event(&mut self, interaction_id: Option<&str>, source_id: &str, source_version: Option<&str>) -> Result<(), Box<dyn Error>> {
        with_locked_state(|state| {
            if state.run_id.is_empty() {
                state.run_id = Uuid::new_v4().to_string();
            }

            let mut trace_file = fs::OpenOptions::new()
                .create(true)
                .write(true)
                .append(true)
                .open(&config_path())?;

            writeln!(trace_file, "{}",
                json!({
                    "run_id": &state.run_id,
                    "sequence": state.sequence_no,
                    "timestamp": SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs(),
                    "journey_id": &state.journey_id,
                    "type": TraceEvent::GuidanceRetrieved.as_ref(),
                    "interaction_id": &interaction_id,
                    "source": {
                        "id": source_id,
                        "version": source_version,
                    }
                })
            )?;

            state.sequence_no += 1;

            Ok(())
        })?;

        Ok(())
    }
}

#[derive(Serialize)]
struct OutputTrace {
    schema_version: String,
    source_trace: String,
    run: OutputRun,
    #[serde(skip_serializing_if = "Option::is_none")]
    initial_context: Option<Value>,
    events: Vec<OutputEvent>,
}

#[derive(Serialize)]
struct OutputRun {
    id: String,
    journey_id: String,
    implementation: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    status: Option<String>,
}

#[derive(Serialize)]
struct SourceRef {
    id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    version: Option<String>,
}

#[derive(Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum OutputEvent {
    InteractionAvailable { interaction_id: String },
    ValuesProposed { #[serde(skip_serializing_if = "Option::is_none")] interaction_id: Option<String>, values: HashMap<String, Value> },
    UserMessage { #[serde(skip_serializing_if = "Option::is_none")] interaction_id: Option<String>, content: String },
    GuidanceRetrieved { #[serde(skip_serializing_if = "Option::is_none")] interaction_id: Option<String>, source: SourceRef },
    AnswerPresented { interaction_id: String },
    ValuesSubmitted { #[serde(skip_serializing_if = "Option::is_none")] interaction_id: Option<String>, values: HashMap<String, Value> },
}

fn values_from(record: &Value) -> HashMap<String, Value> {
    record.get("values")
        .and_then(Value::as_object)
        .map(|obj| obj.clone().into_iter().collect())
        .unwrap_or_default()
}

/// Converts the `run_id` slice of `trace.jsonl` into the richer YAML trace
/// format. Best-effort: fields with no source data today (`initial_context`,
/// `run.status`/`result` — no `JourneyFinished` event is ever emitted yet,
/// `source.version` — spec docs aren't versioned) are omitted rather than
/// fabricated.
pub fn convert_to_yaml(run_id: &str, implementation: &str, output_path: &std::path::Path) -> Result<(), Box<dyn Error>> {
    let source_path = config_path();
    let reader = io::BufReader::new(fs::File::open(&source_path)?);

    let mut journey_id: Option<String> = None;
    let mut events: Vec<OutputEvent> = Vec::new();

    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }

        let record: Value = serde_json::from_str(&line)?;

        if record.get("run_id").and_then(Value::as_str) != Some(run_id) {
            continue;
        }

        // The `start_trace` header line carries no "type" field — skip it.
        let Some(event_type) = record.get("type").and_then(Value::as_str) else {
            continue;
        };

        if journey_id.is_none() {
            match record.get("journey_id").and_then(Value::as_str) {
                Some(j) if !j.is_empty() => journey_id = Some(j.to_string()),
                _ => {}
            }
        }

        let interaction_id = record.get("interaction_id").and_then(Value::as_str).map(String::from);

        let event = match event_type {
            "InteractionAvailable" => interaction_id.map(|interaction_id| OutputEvent::InteractionAvailable { interaction_id }),
            "AnswerPresented" => interaction_id.map(|interaction_id| OutputEvent::AnswerPresented { interaction_id }),
            "ValuesProposed" => Some(OutputEvent::ValuesProposed { interaction_id, values: values_from(&record) }),
            "ValuesSubmitted" => Some(OutputEvent::ValuesSubmitted { interaction_id, values: values_from(&record) }),
            "UserMessage" => Some(OutputEvent::UserMessage {
                interaction_id,
                content: record.get("content").and_then(Value::as_str).unwrap_or("").to_string(),
            }),
            "GuidanceRetrieved" => record.get("source").map(|source| OutputEvent::GuidanceRetrieved {
                interaction_id,
                source: SourceRef {
                    id: source.get("id").and_then(Value::as_str).unwrap_or("").to_string(),
                    version: source.get("version").and_then(Value::as_str).map(String::from),
                },
            }),
            _ => None,
        };

        if let Some(event) = event {
            events.push(event);
        }
    }

    let output = OutputTrace {
        schema_version: "0.1".to_string(),
        source_trace: source_path.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default(),
        run: OutputRun {
            id: run_id.to_string(),
            journey_id: journey_id.unwrap_or_default(),
            implementation: implementation.to_string(),
            status: None,
        },
        initial_context: None,
        events,
    };

    serde_yaml::to_writer(fs::File::create(output_path)?, &output)?;

    Ok(())
}

/// Opens `state_path()`, takes an exclusive lock (blocking until acquired so
/// concurrent writers from either process just wait their turn), reads the
/// current `TraceState`, runs `f`, then persists the mutated state before
/// releasing the lock. `f` does its own `trace.jsonl` append inside the
/// closure so sequence assignment and the write land as one atomic unit —
/// otherwise a later sequence number from one process could hit disk before
/// an earlier one from the other.
fn with_locked_state<T>(f: impl FnOnce(&mut TraceState) -> io::Result<T>) -> io::Result<T> {
    let path = state_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let mut file = fs::OpenOptions::new()
        .create(true)
        .read(true)
        .write(true)
        .open(&path)?;

    FileExt::lock(&file)?;

    let mut contents = String::new();
    file.read_to_string(&mut contents)?;
    let mut state: TraceState = serde_json::from_str(&contents).unwrap_or_default();

    let result = f(&mut state);

    if result.is_ok() {
        let serialized = serde_json::to_string(&state)?;
        file.set_len(0)?;
        file.seek(SeekFrom::Start(0))?;
        file.write_all(serialized.as_bytes())?;
    }

    FileExt::unlock(&file)?;

    result
}

fn config_path() -> std::path::PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("legibility-chat")
        .join("trace.jsonl")
}

fn state_path() -> std::path::PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("legibility-chat")
        .join("trace.state.json")
}
