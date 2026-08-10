// In-chat tool grouping for the Journey feature. This turns the flat message
// list into a render sequence where a run of consecutive tool-call messages
// collapses into a single group, each call annotated with the journey step it
// advanced, and the step pills that follow the reply which closed that run.
//
// This module and its two components (ToolCallGroup, StepPills) are self
// contained: MessageList chooses which to render, and nothing else depends on
// them. Removing this file, the two components, and restoring MessageList's
// original loop reverts the feature completely.

import type { Message } from '../types'
import { parseServicePlan, matchStepNumber, type PlanStep } from './journey'

export interface ToolCallRow {
  message: Message
  // Journey step this call advanced, or null when the call added no step.
  addedStep: number | null
}

export interface ToolGroup {
  id: string
  rows: ToolCallRow[]
  // Distinct step numbers advanced anywhere in this group, in order.
  addedSteps: number[]
}

export type RenderItem =
  | { kind: 'message'; id: string; message: Message }
  | { kind: 'toolGroup'; id: string; group: ToolGroup }
  | { kind: 'stepPills'; id: string; steps: number[] }

// Read the current service plan from the most recent get_service result in the
// conversation. Returns an empty plan when no service has been looked up yet.
function planFromMessages(messages: Message[]): PlanStep[] {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i]
    if (m.role === 'tool-call' && m.toolName === 'get_service' && m.toolResult) {
      return parseServicePlan(m.toolResult)
    }
  }
  return []
}

// Build one group from a run of consecutive tool-call messages. Only a
// successful fetch can advance a step, so every other tool call is marked as
// adding no step.
function makeGroup(run: Message[], plan: PlanStep[]): ToolGroup {
  const rows: ToolCallRow[] = run.map((message) => {
    let addedStep: number | null = null
    if (message.toolName === 'fetch') {
      const args = message.toolArgs as { url?: string } | undefined
      const succeeded = (message.toolResult ?? '').startsWith('HTTP 2')
      if (succeeded && typeof args?.url === 'string') {
        addedStep = matchStepNumber(args.url, plan)
      }
    }
    return { message, addedStep }
  })

  const addedSteps: number[] = []
  for (const row of rows) {
    if (row.addedStep !== null && !addedSteps.includes(row.addedStep)) {
      addedSteps.push(row.addedStep)
    }
  }

  return { id: run[0].id, rows, addedSteps }
}

// Transform the message list into render items. Consecutive tool-call messages
// collapse into one toolGroup. When the assistant reply that closes a run has
// advanced steps, a stepPills item is emitted straight after that reply.
export function buildRenderItems(messages: Message[]): RenderItem[] {
  const plan = planFromMessages(messages)
  const items: RenderItem[] = []
  let pendingSteps: number[] = []
  let index = 0

  while (index < messages.length) {
    const message = messages[index]

    if (message.role === 'tool-call') {
      const run: Message[] = []
      while (index < messages.length && messages[index].role === 'tool-call') {
        run.push(messages[index])
        index += 1
      }
      const group = makeGroup(run, plan)
      items.push({ kind: 'toolGroup', id: group.id, group })
      pendingSteps = group.addedSteps
      continue
    }

    items.push({ kind: 'message', id: message.id, message })

    // A reply that follows a tool run carries the pills for the steps that run
    // advanced. Card replies count as replies here too.
    if ((message.role === 'assistant' || message.role === 'card') && pendingSteps.length > 0) {
      items.push({ kind: 'stepPills', id: `${message.id}-pills`, steps: pendingSteps })
      pendingSteps = []
    }

    index += 1
  }

  return items
}
