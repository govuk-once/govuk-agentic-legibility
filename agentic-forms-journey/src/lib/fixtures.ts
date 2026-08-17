// Sample common traces standing in for other form-filling methods, so the
// comparison page is demonstrable before real traces from other prototypes
// exist. Clearly marked with "example-" implementation names, distinct from
// this app's own implementation identifiers, so they are never mistaken for
// a real run.
//
// Two example journeys, three methods each. All three methods on a journey
// run the SAME field keys, since methods can only be compared fairly when
// they ran the same journey (same questions, same branching).

import { SCHEMA_VERSION, type CommonTrace, type TraceEvent } from "./common-trace";

const POTHOLE = { id: "pothole-report-demo", name: "Report a pothole (example)" };
const BLUE_BADGE = { id: "blue-badge-demo", name: "Apply for a Blue Badge (example)" };

// One interaction becoming available, with no value proposed for it. Used
// for a field that is left for a human (an upload) or never reached.
function available(interactionId: string): TraceEvent {
  return { type: "interaction_available", interaction_id: interactionId };
}

// One interaction becoming available and immediately proposed with a scalar
// value, stored under its own key.
function proposed(interactionId: string, value: unknown): TraceEvent[] {
  return [available(interactionId), { type: "values_proposed", interaction_id: interactionId, values: { [interactionId]: value } }];
}

// The same interaction's value, submitted as final.
function submitted(interactionId: string, value: unknown): TraceEvent {
  return { type: "values_submitted", interaction_id: interactionId, values: { [interactionId]: value } };
}

// ---------------------------------------------------------------------------
// Journey 1: Report a pothole. Straightforward, no required uploads, so
// every method here can reach "completed".
// ---------------------------------------------------------------------------

const potholeAgent: CommonTrace = {
  schema_version: SCHEMA_VERSION,
  source_trace: null,
  run: { id: "example-pothole-agent-1", journey_id: POTHOLE.id, implementation: "example-agent", status: "completed" },
  initial_context: { form: { id: POTHOLE.id, name: POTHOLE.name, sha256: "n/a" } },
  events: [
    ...proposed("hazardType", "Pothole"),
    submitted("hazardType", "Pothole"),
    ...proposed("location", "Kirkstall Road, near number 40"),
    submitted("location", "Kirkstall Road, near number 40"),
    ...proposed("name", "Jen Sykes"),
    submitted("name", "Jen Sykes"),
    // vehicleReg is never reached: the branch for a pothole report skips it.
    // photo is optional and left for the user to add, so it becomes
    // available but never gets a proposed or submitted value.
    available("photo"),
    { type: "journey_finished", status: "completed", result: { hazardType: "Pothole", location: "Kirkstall Road, near number 40", name: "Jen Sykes" } },
    { type: "answer_presented" },
  ],
};

const potholeVerbose: CommonTrace = {
  schema_version: SCHEMA_VERSION,
  source_trace: null,
  run: { id: "example-pothole-verbose-1", journey_id: POTHOLE.id, implementation: "example-verbose-questionnaire", status: "completed" },
  initial_context: { form: { id: POTHOLE.id, name: POTHOLE.name, sha256: "n/a" } },
  events: [
    ...proposed("hazardType", "Pothole"),
    submitted("hazardType", "Pothole"),
    ...proposed("location", "Kirkstall Road, near number 40"),
    submitted("location", "Kirkstall Road, near number 40"),
    ...proposed("name", "Jen Sykes"),
    submitted("name", "Jen Sykes"),
    // Over-collects: asks for the vehicle registration even though the
    // branch would have skipped it, and insists on the optional photo.
    ...proposed("vehicleReg", "Not applicable"),
    submitted("vehicleReg", "Not applicable"),
    ...proposed("photo", "photo-of-pothole.jpg"),
    submitted("photo", "photo-of-pothole.jpg"),
    {
      type: "journey_finished",
      status: "completed",
      result: {
        hazardType: "Pothole",
        location: "Kirkstall Road, near number 40",
        name: "Jen Sykes",
        vehicleReg: "Not applicable",
        photo: "photo-of-pothole.jpg",
      },
    },
    { type: "answer_presented" },
  ],
};

const potholeAggressive: CommonTrace = {
  schema_version: SCHEMA_VERSION,
  source_trace: null,
  run: { id: "example-pothole-aggressive-1", journey_id: POTHOLE.id, implementation: "example-aggressive-autofill", status: "completed" },
  initial_context: { form: { id: POTHOLE.id, name: POTHOLE.name, sha256: "n/a" } },
  events: [
    ...proposed("hazardType", "Pothole"),
    submitted("hazardType", "Pothole"),
    // Guesses a shorter version of the location, so this diverges from the
    // reference in the comparison view.
    ...proposed("location", "Kirkstall Road"),
    submitted("location", "Kirkstall Road"),
    // Guesses a generic name rather than asking, another divergence.
    ...proposed("name", "Customer"),
    submitted("name", "Customer"),
    available("photo"),
    { type: "journey_finished", status: "completed", result: { hazardType: "Pothole", location: "Kirkstall Road", name: "Customer" } },
    { type: "answer_presented" },
  ],
};

// ---------------------------------------------------------------------------
// Journey 2: Apply for a Blue Badge. Branches on the eligibility route and
// needs two document uploads only a human can provide, so every method here
// stays "blocked": the required uploads are always outstanding.
// ---------------------------------------------------------------------------

const badgeAddress = { addressLine1: "1 Example Street", town: "Leeds", postcode: "LS1 4DY" };

const bbAgent: CommonTrace = {
  schema_version: SCHEMA_VERSION,
  source_trace: null,
  run: { id: "example-badge-agent-1", journey_id: BLUE_BADGE.id, implementation: "example-agent", status: "blocked" },
  initial_context: { form: { id: BLUE_BADGE.id, name: BLUE_BADGE.name, sha256: "n/a" } },
  events: [
    ...proposed("applicantType", "For myself"),
    submitted("applicantType", "For myself"),
    ...proposed("eligibilityRoute", "Automatic (receives PIP)"),
    submitted("eligibilityRoute", "Automatic (receives PIP)"),
    ...proposed("name", "Jen Sykes"),
    submitted("name", "Jen Sykes"),
    ...proposed("dob", "1985-04-12"),
    submitted("dob", "1985-04-12"),
    ...proposed("nino", "QQ 12 34 56 C"),
    submitted("nino", "QQ 12 34 56 C"),
    available("address"),
    { type: "values_proposed", interaction_id: "address", values: badgeAddress },
    { type: "values_submitted", interaction_id: "address", values: badgeAddress },
    // mobilityDetails is never reached: the automatic PIP route skips it.
    // Both uploads become available but stay unfilled, so the journey
    // cannot reach "completed".
    available("benefitProof"),
    available("photo"),
  ],
};

const bbVerbose: CommonTrace = {
  schema_version: SCHEMA_VERSION,
  source_trace: null,
  run: { id: "example-badge-verbose-1", journey_id: BLUE_BADGE.id, implementation: "example-verbose-questionnaire", status: "blocked" },
  initial_context: { form: { id: BLUE_BADGE.id, name: BLUE_BADGE.name, sha256: "n/a" } },
  events: [
    ...proposed("applicantType", "For myself"),
    submitted("applicantType", "For myself"),
    ...proposed("eligibilityRoute", "Automatic (receives PIP)"),
    submitted("eligibilityRoute", "Automatic (receives PIP)"),
    ...proposed("name", "Jen Sykes"),
    submitted("name", "Jen Sykes"),
    ...proposed("dob", "1985-04-12"),
    submitted("dob", "1985-04-12"),
    ...proposed("nino", "QQ 12 34 56 C"),
    submitted("nino", "QQ 12 34 56 C"),
    available("address"),
    { type: "values_proposed", interaction_id: "address", values: badgeAddress },
    { type: "values_submitted", interaction_id: "address", values: badgeAddress },
    // Over-collects: asks for a mobility assessment despite the automatic
    // route making it unnecessary.
    ...proposed("mobilityDetails", "Struggles to walk far without support."),
    submitted("mobilityDetails", "Struggles to walk far without support."),
    available("benefitProof"),
    available("photo"),
  ],
};

const bbAggressive: CommonTrace = {
  schema_version: SCHEMA_VERSION,
  source_trace: null,
  run: { id: "example-badge-aggressive-1", journey_id: BLUE_BADGE.id, implementation: "example-aggressive-autofill", status: "blocked" },
  initial_context: { form: { id: BLUE_BADGE.id, name: BLUE_BADGE.name, sha256: "n/a" } },
  events: [
    ...proposed("applicantType", "For myself"),
    submitted("applicantType", "For myself"),
    ...proposed("eligibilityRoute", "Automatic (receives PIP)"),
    submitted("eligibilityRoute", "Automatic (receives PIP)"),
    ...proposed("name", "Jen Sykes"),
    submitted("name", "Jen Sykes"),
    ...proposed("dob", "1985-04-12"),
    submitted("dob", "1985-04-12"),
    // Guesses a National Insurance number, a genuine divergence from the
    // reference's real one.
    ...proposed("nino", "QQ 99 88 77 C"),
    submitted("nino", "QQ 99 88 77 C"),
    available("address"),
    { type: "values_proposed", interaction_id: "address", values: badgeAddress },
    { type: "values_submitted", interaction_id: "address", values: badgeAddress },
    available("benefitProof"),
    available("photo"),
  ],
};

// The sample methods offered by the "Load sample methods" button on
// /compare. Two example journeys, three methods each, so the journey-by-
// journey grouping and the journey selector are demonstrable, and each set
// compares fairly within its journey.
export const SAMPLE_METHODS: CommonTrace[] = [
  potholeAgent,
  potholeVerbose,
  potholeAggressive,
  bbAgent,
  bbVerbose,
  bbAggressive,
];
