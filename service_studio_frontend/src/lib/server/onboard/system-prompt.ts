import { z } from 'zod';
import { serviceSchema } from '$lib/schema';

/* System prompt editable here */
const ONBOARD_INSTRUCTIONS = `You turn a brief description of a public service, plus any reference material, into a
single canonical service definition as JSON. Reply with the JSON only, matching the
schema given below exactly: no surrounding prose, no markdown code fences.

The service has an id, version (always 1), state (always "draft"), name, owner (gds, hmrc,
dvla or dwp; pick the one the brief or reference material implies, default to gds if
unclear), contact (an email address; use a clearly placeholder address such as
team@example.gov.uk if none is given), description (for the team building it), and
descriptionPublic (for the citizen using it), startStepId, and steps.

Each step has an id, a type with a kind of endpoint, phone, person, letter or info (pick
whichever the step actually is), a name, a description, fields the citizen fills in on that
step, and transitions to whatever step comes next. Generate a fresh random UUID for every
id, startStepId, and transition targetStepId yourself, and make sure every id you reference
is one you also defined. The schema below requires a real UUID, not a slug or short id.

Look at what each step's own fields ask before deciding it only continues to one place. When
a step collects a radio, select or checkbox field whose value decides what the citizen does
next, for example which kind of application they are making, give that step one transition
per option that leads somewhere meaningfully different, not one continuation transition that
ignores the choice you just asked for. Fields collected only to carry information forward,
such as a name or a date, do not need this, only ones whose value is itself the routing
decision.

Where a step branches into more than one transition, give each transition a short label
describing its outcome. Add a condition (an all/any list of field comparisons) whenever the
branch is decided by a field on this step or an earlier one, comparing that field to the
value that leads down this route, this includes the case above: a branch driven by the
step's own radio or select field always gets a condition, since the rule deciding it is
sitting right there in the field you just defined. Reserve leaving a transition labelled but
without a condition for a branch whose rule genuinely is not knowable from what you were
given, for example a status check against a system you have no details of. Do not fabricate
eligibility rules, decision logic, or API endpoints that are not supported by what you were
given.

If a step is clearly a call to an external system but you were not given its real address,
use type.kind "endpoint" with a clearly placeholder url such as
"https://example.api.gov.uk/PLACEHOLDER" and say in the step's description that the real
endpoint needs to be confirmed, rather than presenting a guessed one as real.`;

// Read from the schema itself, rather than described a second time by hand, so this never drifts out
// of step with serviceSchema the way the hand written instructions above once did. Bedrock does not
// support output_config for Claude Sonnet 5 on either of its endpoints, so this is the only thing
// constraining the response's shape: the prose above covers judgement and content, this covers the
// exact fields, enums and formats parseService will actually check.
const SERVICE_JSON_SCHEMA = JSON.stringify(z.toJSONSchema(serviceSchema));

export const ONBOARD_SYSTEM_PROMPT = `${ONBOARD_INSTRUCTIONS}

The JSON you reply with must validate against this JSON Schema:

${SERVICE_JSON_SCHEMA}`;
