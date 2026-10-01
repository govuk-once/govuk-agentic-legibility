import { buildBaseToolDefs, buildEscalationToolDef, type ToolContext, type ToolDef } from './tool-defs';

// Autonomous /agentic resume-loop tool set — the 7 base tools plus escalate_to_human.
// Kept as a compile-time-separate export from tools.ts so the "chat can never
// escalate, only the autonomous loop can" split can't drift at the call site.
export function buildAgenticTools(ctx: ToolContext): ToolDef[] {
  return [...buildBaseToolDefs(ctx), buildEscalationToolDef(ctx)];
}
