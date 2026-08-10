// Journey derivation for the Journey panel. The panel shows the steps of the
// service the assistant is working through, and how far it has progressed. All
// of this is read from data the frontend already holds: the get_service tool
// result gives the plan, and the fetch tool calls show which steps have run.
// There are no backend changes behind this. Field-level provenance (who
// supplied each answer) is deliberately not derived here, it needs a dedicated
// backend signal and is mocked in the panel for design review only.

export type StepStatus = 'done' | 'active' | 'awaiting'

export interface PlanStep {
  number: number
  endpoint: string
  title: string
  department: string
  required: boolean
  note?: string
}

export interface JourneyStep extends PlanStep {
  status: StepStatus
  // Compact response body from the fetch that completed this step, when one ran.
  result?: string
}

export interface FetchCall {
  url: string
  ok: boolean
  result: string
}

// Turn an endpoint identifier such as "choose_address_entry_method" into a
// readable title such as "Choose address entry method". Used as the step title
// until the backend can supply a friendlier summary.
function humaniseEndpoint(endpoint: string): string {
  if (!endpoint) return ''
  const spaced = endpoint.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

// Reduce an endpoint or URL segment to letters only so that the underscore form
// used in service files ("find_address_by_postcode") and the hyphen form used
// in request URLs ("find-address-by-postcode") compare equal.
function normaliseEndpoint(value: string): string {
  return value.replace(/[-_\s]/g, '').toLowerCase()
}

// Reduce a fetch response to a single short line for display beneath a step.
// The leading "HTTP 200" status line is dropped and whitespace is collapsed, so
// what remains is the response body the step produced.
function summariseResult(raw: string): string {
  const body = raw.replace(/^HTTP\s+\d+\s*/i, '').trim()
  const collapsed = body.replace(/\s+/g, ' ')
  return collapsed.length > 140 ? `${collapsed.slice(0, 140)}…` : collapsed
}

// Take the last path segment of a request URL, e.g.
// "http://localhost:8127/choose-address-entry-method" -> "choose-address-entry-method".
// Falls back to the raw string if the URL cannot be parsed.
function lastPathSegment(url: string): string {
  try {
    const segments = new URL(url).pathname.split('/').filter(Boolean)
    return segments[segments.length - 1] ?? ''
  } catch {
    return url
  }
}

// Parse a get_service result body into its ordered steps. Each step is one
// numbered line of the form "N. <uuid>, <endpoint>, <department>, required",
// optionally followed by prose lines describing that step. The required flag is
// read from the tail of the line rather than a fixed column, so a line that
// omits the comma before "required" is still handled correctly.
export function parseServicePlan(text: string): PlanStep[] {
  const steps: PlanStep[] = []

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    const stepMatch = line.match(/^(\d+)\.\s*(.+)$/)

    if (stepMatch) {
      const parts = stepMatch[2].split(',').map((part) => part.trim())
      // parts[0] is the step's own uuid, which the panel does not need.
      const endpoint = parts[1] ?? ''
      if (!endpoint) continue

      // Everything after the endpoint holds the department and the
      // required/optional flag, whether or not a comma separates them.
      const tail = parts.slice(2).join(' ')
      const department = tail.split(/\s+/)[0] ?? ''
      const required = /\brequired\b/i.test(tail)

      steps.push({
        number: parseInt(stepMatch[1], 10),
        endpoint,
        title: humaniseEndpoint(endpoint),
        department,
        required,
      })
    } else if (line && steps.length > 0) {
      // A non-numbered line describes the step directly above it.
      const current = steps[steps.length - 1]
      current.note = current.note ? `${current.note} ${line}` : line
    }
  }

  return steps
}

// Assign a status to each plan step from the fetch calls made so far. A step is
// done once a successful fetch has targeted its endpoint. The earliest step that
// is not yet done is treated as active, and every step after it is awaiting. The
// endpoint match is a step-level heuristic: it confirms a step ran, not which
// individual fields it filled.
export function computeStepProgress(plan: PlanStep[], fetches: FetchCall[]): JourneyStep[] {
  // Map each completed step number to the response body of the fetch that
  // completed it. A later successful fetch to the same endpoint replaces an
  // earlier one, so the most recent result is what shows.
  const results = new Map<number, string>()

  for (const call of fetches) {
    if (!call.ok) continue
    const target = normaliseEndpoint(lastPathSegment(call.url))
    if (!target) continue
    for (const step of plan) {
      const stepKey = normaliseEndpoint(step.endpoint)
      if (stepKey && (target.includes(stepKey) || stepKey.includes(target))) {
        results.set(step.number, summariseResult(call.result))
      }
    }
  }

  let activeAssigned = false
  return plan.map((step) => {
    let status: StepStatus
    if (results.has(step.number)) {
      status = 'done'
    } else if (!activeAssigned) {
      status = 'active'
      activeAssigned = true
    } else {
      status = 'awaiting'
    }
    return { ...step, status, result: results.get(step.number) }
  })
}
