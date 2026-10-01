import { buildBaseToolDefs, type ToolContext, type ToolDef } from './tool-defs';

// Chat tool set — the 7 base tools, no escalate_to_human.
export function buildChatTools(ctx: ToolContext): ToolDef[] {
  return buildBaseToolDefs(ctx);
}
