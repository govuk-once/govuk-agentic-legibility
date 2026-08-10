// Synthetic RunLogs standing in for other form-filling methods, so the
// comparison page is demonstrable before real logs from other POCs exist.
//
// All three are AGENTIC methods running the SAME example form ("Report a
// pothole"), with the SAME field keys. That is deliberate: methods can only be
// compared fairly when they ran the same form (same questions, same branching),
// so a self-contained same-form set is what makes the comparison meaningful.
//
// They are three genuinely different strategies:
//   - claude-conversational-agent: infers what it can, asks only for the
//     genuinely personal unknown, follows branching to skip what no longer applies.
//   - verbose-questionnaire: asks one question per field and over-collects.
//   - aggressive-autofill: fills everything in one pass by guessing, asks
//     nothing, but flags its guesses for a human to confirm.

import type { RunLog } from "./run-log";

const FORM = { id: "pothole-report-demo", name: "Report a pothole (example)" };

const claudeAgent: RunLog = {
  schemaVersion: 1,
  method: "claude-conversational-agent",
  description:
    "Inference-first agent. Works out everything it can from a short chat, asks the citizen only for genuinely personal unknowns, and follows the form's branching to skip questions that no longer apply.",
  form: FORM,
  model: "claude-sonnet-5",
  exportedAt: null,
  criteria: {
    performance: {
      totals: { turns: 2, inputTokens: 3120, outputTokens: 480, totalTokens: 3600, wallMs: 4200 },
      turns: [
        { turn: 1, model: "claude-sonnet-5", latencyMs: 2600, inputTokens: 1500, outputTokens: 240 },
        { turn: 2, model: "claude-sonnet-5", latencyMs: 1600, inputTokens: 1620, outputTokens: 240 },
      ],
    },
    conversationHistory: [
      { role: "user", content: "Report a pothole on Kirkstall Road, near number 40." },
      { role: "assistant", content: "Thanks, what's your name so I can attach it to the report?" },
      { role: "user", content: "Jen Sykes" },
      { role: "assistant", content: "Great, Jen. That's everything, ready to submit." },
    ],
    interaction: [
      { turn: 1, user: "Report a pothole on Kirkstall Road, near number 40.", agent: "Thanks, what's your name so I can attach it to the report?", awaitingInput: true, newFields: ["hazardType", "location"] },
      { turn: 2, user: "Jen Sykes", agent: "Great, Jen. That's everything, ready to submit.", awaitingInput: false, newFields: ["name"] },
    ],
    agentActions: [
      { field: "hazardType", questionText: "What are you reporting?", answerType: "selection", action: "filled", detail: "Pothole", needsHuman: false },
      { field: "location", questionText: "Where is the problem?", answerType: "text", action: "filled", detail: "Kirkstall Road, near number 40", needsHuman: false },
      { field: "name", questionText: "Your name", answerType: "name", action: "filled", detail: "Jen Sykes", needsHuman: false },
      { field: "vehicleReg", questionText: "Vehicle registration", answerType: "text", action: "skipped", detail: "Skipped: a pothole report is not vehicle-related.", needsHuman: false },
      { field: "photo", questionText: "Upload a photo (optional)", answerType: "file", action: "needs-answer", detail: "Optional: left for the citizen to add.", needsHuman: false },
    ],
    executorActions: { available: false, note: "Submit simulated, no executor in this POC.", actions: [] },
  },
};

const verboseQuestionnaire: RunLog = {
  schemaVersion: 1,
  method: "verbose-questionnaire",
  description:
    "Turns the form back into an interrogation: asks one question per field instead of inferring, spends many turns and tokens, and over-collects, capturing a vehicle registration and photo the branching made unnecessary.",
  form: FORM,
  model: "gpt-style-verbose",
  exportedAt: null,
  criteria: {
    performance: {
      totals: { turns: 5, inputTokens: 9200, outputTokens: 1300, totalTokens: 10500, wallMs: 13400 },
      turns: [
        { turn: 1, model: "gpt-style-verbose", latencyMs: 2900, inputTokens: 1400, outputTokens: 260 },
        { turn: 2, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 1700, outputTokens: 240 },
        { turn: 3, model: "gpt-style-verbose", latencyMs: 2700, inputTokens: 1900, outputTokens: 260 },
        { turn: 4, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 2000, outputTokens: 260 },
        { turn: 5, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 2200, outputTokens: 280 },
      ],
    },
    conversationHistory: [
      { role: "user", content: "I want to report a pothole." },
      { role: "assistant", content: "What are you reporting?" },
      { role: "user", content: "A pothole." },
      { role: "assistant", content: "Where is the problem?" },
      { role: "user", content: "Kirkstall Road, near number 40." },
      { role: "assistant", content: "What is your full name?" },
      { role: "user", content: "Jen Sykes." },
      { role: "assistant", content: "What is your vehicle registration?" },
      { role: "user", content: "It's a pothole, not a vehicle." },
      { role: "assistant", content: "Please upload a photo of the pothole." },
    ],
    interaction: [
      { turn: 1, user: "I want to report a pothole.", agent: "What are you reporting?", awaitingInput: true, newFields: [] },
      { turn: 2, user: "A pothole.", agent: "Where is the problem?", awaitingInput: true, newFields: ["hazardType"] },
      { turn: 3, user: "Kirkstall Road, near number 40.", agent: "What is your full name?", awaitingInput: true, newFields: ["location"] },
      { turn: 4, user: "Jen Sykes.", agent: "What is your vehicle registration?", awaitingInput: true, newFields: ["name"] },
      { turn: 5, user: "It's a pothole, not a vehicle.", agent: "Please upload a photo of the pothole.", awaitingInput: true, newFields: ["vehicleReg", "photo"] },
    ],
    agentActions: [
      { field: "hazardType", questionText: "What are you reporting?", answerType: "selection", action: "filled", detail: "Pothole", needsHuman: false },
      { field: "location", questionText: "Where is the problem?", answerType: "text", action: "filled", detail: "Kirkstall Road, near number 40", needsHuman: false },
      { field: "name", questionText: "Your name", answerType: "name", action: "filled", detail: "Jen Sykes", needsHuman: false },
      { field: "vehicleReg", questionText: "Vehicle registration", answerType: "text", action: "filled", detail: "Collected despite the branch making it unnecessary.", needsHuman: false },
      { field: "photo", questionText: "Upload a photo (optional)", answerType: "file", action: "filled", detail: "Insisted on a photo the form marks optional.", needsHuman: false },
    ],
    executorActions: { available: false, note: "Submit simulated, no executor in this POC.", actions: [] },
  },
};

const aggressiveAutofill: RunLog = {
  schemaVersion: 1,
  method: "aggressive-autofill",
  description:
    "Fills every field in a single pass by guessing from context and defaults, asking nothing. Fast, but flags the values it guessed for a human to confirm before submitting.",
  form: FORM,
  model: "fast-autofill",
  exportedAt: null,
  criteria: {
    performance: {
      totals: { turns: 1, inputTokens: 1700, outputTokens: 300, totalTokens: 2000, wallMs: 1800 },
      turns: [{ turn: 1, model: "fast-autofill", latencyMs: 1800, inputTokens: 1700, outputTokens: 300 }],
    },
    conversationHistory: [
      { role: "user", content: "Report a pothole on Kirkstall Road." },
      { role: "assistant", content: "I've filled everything in. Please review the details I guessed before submitting." },
    ],
    interaction: [
      { turn: 1, user: "Report a pothole on Kirkstall Road.", agent: "I've filled everything in. Please review the details I guessed before submitting.", awaitingInput: false, newFields: ["hazardType", "location", "name"] },
    ],
    agentActions: [
      { field: "hazardType", questionText: "What are you reporting?", answerType: "selection", action: "filled", detail: "Pothole", needsHuman: false },
      { field: "location", questionText: "Where is the problem?", answerType: "text", action: "filled", detail: "Kirkstall Road (exact spot guessed)", needsHuman: true },
      { field: "name", questionText: "Your name", answerType: "name", action: "filled", detail: "Guessed from the account (unconfirmed).", needsHuman: true },
      { field: "vehicleReg", questionText: "Vehicle registration", answerType: "text", action: "skipped", detail: "Skipped by branch.", needsHuman: false },
      { field: "photo", questionText: "Upload a photo (optional)", answerType: "file", action: "needs-answer", detail: "Optional: not added.", needsHuman: false },
    ],
    executorActions: { available: false, note: "Submit simulated, no executor in this POC.", actions: [] },
  },
};

// ---------------------------------------------------------------------------
// A second, more complex example form: "Apply for a Blue Badge". It branches on
// the eligibility route (automatic vs further assessment) and needs document
// uploads only a human can provide, so it shows "left for a human to fill in"
// (the uploads) as well as the confirm-heavy behaviour of the aggressive method.
// ---------------------------------------------------------------------------

const BLUE_BADGE = { id: "blue-badge-demo", name: "Apply for a Blue Badge (example)" };

const bbClaudeAgent: RunLog = {
  schemaVersion: 1,
  method: "claude-conversational-agent",
  description:
    "Inference-first agent. Works out the eligibility route from what the citizen says, expands the address from a postcode, and asks only for the identifiers it cannot know, leaving the required uploads for the citizen.",
  form: BLUE_BADGE,
  model: "claude-sonnet-5",
  exportedAt: null,
  criteria: {
    performance: {
      totals: { turns: 2, inputTokens: 3400, outputTokens: 520, totalTokens: 3920, wallMs: 6000 },
      turns: [
        { turn: 1, model: "claude-sonnet-5", latencyMs: 3200, inputTokens: 1700, outputTokens: 260 },
        { turn: 2, model: "claude-sonnet-5", latencyMs: 2800, inputTokens: 1700, outputTokens: 260 },
      ],
    },
    conversationHistory: [
      { role: "user", content: "I want to apply for a Blue Badge for myself. I get PIP." },
      { role: "assistant", content: "Thanks, what's your full name, date of birth, National Insurance number and postcode?" },
      { role: "user", content: "Jen Sykes, 12 April 1985, QQ 12 34 56 C, LS1 4DY." },
      { role: "assistant", content: "Got it, you qualify automatically through PIP. You'll just need to upload proof of your PIP award and a passport-style photo to finish." },
    ],
    interaction: [
      { turn: 1, user: "I want to apply for a Blue Badge for myself. I get PIP.", agent: "Thanks, what's your full name, date of birth, National Insurance number and postcode?", awaitingInput: true, newFields: ["applicantType", "eligibilityRoute"] },
      { turn: 2, user: "Jen Sykes, 12 April 1985, QQ 12 34 56 C, LS1 4DY.", agent: "Got it, you qualify automatically through PIP. You'll just need to upload proof of your PIP award and a passport-style photo to finish.", awaitingInput: true, newFields: ["name", "dob", "nino", "address"] },
    ],
    agentActions: [
      { field: "applicantType", questionText: "Who is the badge for?", answerType: "selection", action: "filled", detail: "For myself", needsHuman: false },
      { field: "eligibilityRoute", questionText: "How do you qualify?", answerType: "selection", action: "filled", detail: "Automatic (receives PIP)", needsHuman: false },
      { field: "name", questionText: "Full name", answerType: "name", action: "filled", detail: "Jen Sykes", needsHuman: false },
      { field: "dob", questionText: "Date of birth", answerType: "date", action: "filled", detail: "1985-04-12", needsHuman: false },
      { field: "nino", questionText: "National Insurance number", answerType: "national_insurance_number", action: "filled", detail: "QQ 12 34 56 C", needsHuman: false },
      { field: "address", questionText: "Home address", answerType: "address", action: "filled", detail: "Expanded from postcode LS1 4DY", needsHuman: false },
      { field: "mobilityDetails", questionText: "Describe your mobility difficulties", answerType: "text", action: "skipped", detail: "Skipped: automatic route via PIP does not need an assessment.", needsHuman: false },
      { field: "benefitProof", questionText: "Upload proof of your benefit", answerType: "file", action: "needs-answer", detail: "The citizen must upload their PIP award letter.", needsHuman: true },
      { field: "photo", questionText: "Upload a passport-style photo", answerType: "file", action: "needs-answer", detail: "The citizen must upload a photo.", needsHuman: true },
    ],
    executorActions: { available: false, note: "Submit simulated, no executor in this POC.", actions: [] },
  },
};

const bbVerboseQuestionnaire: RunLog = {
  schemaVersion: 1,
  method: "verbose-questionnaire",
  description:
    "Asks one question per field and over-collects: it takes a mobility-assessment description even though the automatic PIP route makes it unnecessary.",
  form: BLUE_BADGE,
  model: "gpt-style-verbose",
  exportedAt: null,
  criteria: {
    performance: {
      totals: { turns: 8, inputTokens: 14800, outputTokens: 2100, totalTokens: 16900, wallMs: 21000 },
      turns: [
        { turn: 1, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 1500, outputTokens: 240 },
        { turn: 2, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 1700, outputTokens: 250 },
        { turn: 3, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 1800, outputTokens: 260 },
        { turn: 4, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 1850, outputTokens: 260 },
        { turn: 5, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 1900, outputTokens: 270 },
        { turn: 6, model: "gpt-style-verbose", latencyMs: 2600, inputTokens: 1950, outputTokens: 270 },
        { turn: 7, model: "gpt-style-verbose", latencyMs: 2700, inputTokens: 2000, outputTokens: 275 },
        { turn: 8, model: "gpt-style-verbose", latencyMs: 2700, inputTokens: 2100, outputTokens: 275 },
      ],
    },
    conversationHistory: [
      { role: "user", content: "Blue Badge application please." },
      { role: "assistant", content: "Who is the badge for?" },
      { role: "user", content: "Me." },
      { role: "assistant", content: "How do you qualify?" },
    ],
    interaction: [
      { turn: 1, user: "Blue Badge application please.", agent: "Who is the badge for?", awaitingInput: true, newFields: [] },
      { turn: 2, user: "Me.", agent: "How do you qualify?", awaitingInput: true, newFields: ["applicantType"] },
      { turn: 3, user: "I get PIP.", agent: "What is your full name?", awaitingInput: true, newFields: ["eligibilityRoute"] },
      { turn: 4, user: "Jen Sykes.", agent: "What is your date of birth?", awaitingInput: true, newFields: ["name"] },
      { turn: 5, user: "12 April 1985.", agent: "What is your National Insurance number?", awaitingInput: true, newFields: ["dob"] },
      { turn: 6, user: "QQ 12 34 56 C.", agent: "What is your full address?", awaitingInput: true, newFields: ["nino"] },
      { turn: 7, user: "1 Example Street, Leeds, LS1 4DY.", agent: "Please describe your mobility difficulties.", awaitingInput: true, newFields: ["address"] },
      { turn: 8, user: "I struggle to walk far.", agent: "Please upload proof of your benefit and a photo.", awaitingInput: true, newFields: ["mobilityDetails"] },
    ],
    agentActions: [
      { field: "applicantType", questionText: "Who is the badge for?", answerType: "selection", action: "filled", detail: "For myself", needsHuman: false },
      { field: "eligibilityRoute", questionText: "How do you qualify?", answerType: "selection", action: "filled", detail: "Automatic (receives PIP)", needsHuman: false },
      { field: "name", questionText: "Full name", answerType: "name", action: "filled", detail: "Jen Sykes", needsHuman: false },
      { field: "dob", questionText: "Date of birth", answerType: "date", action: "filled", detail: "1985-04-12", needsHuman: false },
      { field: "nino", questionText: "National Insurance number", answerType: "national_insurance_number", action: "filled", detail: "QQ 12 34 56 C", needsHuman: false },
      { field: "address", questionText: "Home address", answerType: "address", action: "filled", detail: "1 Example Street, Leeds, LS1 4DY", needsHuman: false },
      { field: "mobilityDetails", questionText: "Describe your mobility difficulties", answerType: "text", action: "filled", detail: "Collected despite the automatic route making it unnecessary.", needsHuman: false },
      { field: "benefitProof", questionText: "Upload proof of your benefit", answerType: "file", action: "needs-answer", detail: "The citizen must upload their PIP award letter.", needsHuman: true },
      { field: "photo", questionText: "Upload a passport-style photo", answerType: "file", action: "needs-answer", detail: "The citizen must upload a photo.", needsHuman: true },
    ],
    executorActions: { available: false, note: "Submit simulated, no executor in this POC.", actions: [] },
  },
};

const bbAggressiveAutofill: RunLog = {
  schemaVersion: 1,
  method: "aggressive-autofill",
  description:
    "Guesses every personal detail in one pass (including the National Insurance number and eligibility route) and flags them for a human to confirm. Fast, but risky on a form like this.",
  form: BLUE_BADGE,
  model: "fast-autofill",
  exportedAt: null,
  criteria: {
    performance: {
      totals: { turns: 1, inputTokens: 2000, outputTokens: 340, totalTokens: 2340, wallMs: 2100 },
      turns: [{ turn: 1, model: "fast-autofill", latencyMs: 2100, inputTokens: 2000, outputTokens: 340 }],
    },
    conversationHistory: [
      { role: "user", content: "Apply for a Blue Badge for me." },
      { role: "assistant", content: "I've filled everything I could guess. Please check the details, especially your National Insurance number, before submitting." },
    ],
    interaction: [
      { turn: 1, user: "Apply for a Blue Badge for me.", agent: "I've filled everything I could guess. Please check the details, especially your National Insurance number, before submitting.", awaitingInput: false, newFields: ["applicantType", "eligibilityRoute", "name", "dob", "nino", "address"] },
    ],
    agentActions: [
      { field: "applicantType", questionText: "Who is the badge for?", answerType: "selection", action: "filled", detail: "For myself", needsHuman: false },
      { field: "eligibilityRoute", questionText: "How do you qualify?", answerType: "selection", action: "filled", detail: "Automatic (guessed, unconfirmed)", needsHuman: true },
      { field: "name", questionText: "Full name", answerType: "name", action: "filled", detail: "Guessed from the account (unconfirmed).", needsHuman: true },
      { field: "dob", questionText: "Date of birth", answerType: "date", action: "filled", detail: "Guessed (unconfirmed).", needsHuman: true },
      { field: "nino", questionText: "National Insurance number", answerType: "national_insurance_number", action: "filled", detail: "Guessed a NINO (must be verified).", needsHuman: true },
      { field: "address", questionText: "Home address", answerType: "address", action: "filled", detail: "Guessed from the account (unconfirmed).", needsHuman: true },
      { field: "mobilityDetails", questionText: "Describe your mobility difficulties", answerType: "text", action: "skipped", detail: "Skipped by branch (assumed automatic route).", needsHuman: false },
      { field: "benefitProof", questionText: "Upload proof of your benefit", answerType: "file", action: "needs-answer", detail: "The citizen must upload their PIP award letter.", needsHuman: true },
      { field: "photo", questionText: "Upload a passport-style photo", answerType: "file", action: "needs-answer", detail: "The citizen must upload a photo.", needsHuman: true },
    ],
    executorActions: { available: false, note: "Submit simulated, no executor in this POC.", actions: [] },
  },
};

// The sample methods offered by the "Load sample methods" button on /compare.
// Two example forms, three methods each, so the form-by-form grouping and the
// form selector are demonstrable, and each set compares fairly within its form.
export const SAMPLE_METHODS: RunLog[] = [
  claudeAgent,
  verboseQuestionnaire,
  aggressiveAutofill,
  bbClaudeAgent,
  bbVerboseQuestionnaire,
  bbAggressiveAutofill,
];
