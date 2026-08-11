use serde_json::json;
use std::{
    fs,
    time::{
        Duration,
        SystemTime
    },
    io,
    io::{
        Write,
        Error as IoError
    },
    error::Error
};
use uuid::Uuid;

use strum::{
    Display,
    AsRefStr
};

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

// Not useful for testing, as it has to be hard-coded
#[derive(Display, AsRefStr)]
enum TraceInteractionId {
    ChooseAddressEntryMethod,
    FindAddressByPostcode,
    ConfirmNewAddress
}

pub struct Tracer {
    // Also refered to as run_id
    id: String,
    version: String,
    journey_id: String, 
    sequence_no: u32,
}

impl Tracer {
    pub fn new() -> Tracer {
        Self {
           id: Uuid::new_v4().to_string(),
           version: String::from("0.1"),
           journey_id: String::from(""),
           sequence_no: 0
        }
    }

    pub fn set_journey(&mut self, journey: &str) {
       self.journey_id = String::from(journey);
    }


    pub fn start_trace(&mut self) -> io::Result<()> {
        // write the header info to the trace file
        // set the initial context
        let mut trace_file = fs::OpenOptions::new()
            .create(true)
            .write(true)
            .open(&config_path())?;

        writeln!(trace_file, "{}",
            json!({
                "run_id": &self.id,
                "sequence": &self.sequence_no,
                "timestamp": SystemTime::now(),
                "trace_version": &self.version,
                "journey_id": &self.journey_id,
                "consumer": "agent_assisted_chat",
            })
        );
        
        self.sequence_no += 1;

        Ok(())
    }

    pub fn add_event(&mut self, event_type: TraceEvent, content: &str, request_body: Vec<(&str, &str)>) -> Result<(), Box<dyn Error>> {
        // Add a single line to JSONL trace file
        let mut trace_file = fs::OpenOptions::new()
            .create(true)
            .write(true)
            .open(&config_path())?;

        writeln!(trace_file, "{}",
            json!({
                "run_id": &self.id,
                "sequence": &self.sequence_no,
                "timestamp": SystemTime::now(),
                "journey_id": &self.journey_id,
                "type": event_type.as_ref(),
                // chat content from user (UserMessage only)
                "content": &content, 
                // request values if tool is called
                "values": request_body 
            })
        );


        self.sequence_no += 1;

        Ok(())
    }

    fn convert_to_common_trace() {

    }
}

fn config_path() -> std::path::PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("legibility-chat")
        .join("trace.jsonl")
}
