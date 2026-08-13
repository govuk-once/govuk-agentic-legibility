import { env } from "$env/dynamic/private";
import { LlmChatSchema } from "$lib/schemas";
import type { AgentContract, ChatFillResult, ChatMessage } from "./engine-types";

// Builds a forced-tool schema from the actual form fields, so the model is
// guided to put each value in the right field (key, type, enum, object shape,
// and the question text as a description) rather than guessing.
function buildProgressTool(contract: AgentContract) {
  const schemaProperties = (contract.schema.properties ?? {}) as Record<string, unknown>;
  const answerProperties: Record<string, unknown> = {};

  for (const row of contract.mapping) {
    const fragment = schemaProperties[row.key];
    const base =
      fragment && typeof fragment === "object" ? (fragment as Record<string, unknown>) : { type: "string" };
    answerProperties[row.key] = { ...base, description: row.questionText };
  }

  return {
    name: "record_progress",
    description: "Record the answers filled so far and the reply to show the citizen.",
    input_schema: {
      type: "object",
      properties: {
        final_answers: {
          type: "object",
          description:
            "The form answers you have so far, keyed by field key. Only include a field once you actually have its value; omit the rest.",
          properties: answerProperties,
        },
        reply: { type: "string", description: "The message the citizen will read." },
        awaiting_input: {
          type: "boolean",
          description: "True if you still need information from the citizen.",
        },
      },
      required: ["final_answers", "reply", "awaiting_input"],
    },
  };
}

// Tidies the user-facing chat reply: turns any literal "\n" escape sequences the
// model typed into real newlines and collapses excess blank lines.
function cleanReply(reply: string): string {
  return reply
    .replace(/\\r\\n|\\n|\\r/g, "\n")
    .replace(/\r\n?/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// The agent brief: fill what it can, infer where sensible, and only ask the
// user for the minimum it genuinely cannot work out on its own.
const SYSTEM_BRIEF = [
  "You are a capable AI agent completing a UK government form on behalf of a citizen through a short chat.",
  "You are given the form's fields (mapping), its answer schema, and its branching rules.",
  "Your job is to do the work FOR the citizen, not to turn the form back into a questionnaire.",
  "",
  "Inference and defaults come FIRST. Before asking anything, fill in everything you can work out:",
  "- Derive values from what the citizen said. Split a full name into first and last name. Expand an address from a postcode plus a building number or name. Normalise dates, phone numbers, registrations, and formats.",
  "- Choose sensible defaults instead of asking when a citizen would not reasonably care. If no start date is given, default to today (as soon as possible). Infer the permit/application type from the context of their request when it is obvious.",
  "- Work out which branch applies from what they have told you, and only gather the fields that branch actually needs.",
  "",
  "Recognise common UK formats so you map each value to the RIGHT field. A postcode looks like \"G42 8UD\" or \"SW1A 1AA\" and belongs in the postcode part of an address. A vehicle registration looks like \"AB12 CDE\". Do not confuse them. If the citizen gives a postcode, place it in the address and ask only for the remaining address parts you still need (such as the building number or name and the street).",
  "",
  "Then ask for ONLY the genuinely personal facts you cannot know or default — typically the person's name and any unique identifiers the form requires (for example a vehicle registration).",
  "- Ask for these together in ONE short, natural sentence or two.",
  "- NEVER reply with a numbered or bulleted list of fields, and never read the form's field names back to the citizen. That is exactly what we are trying to avoid.",
  "- Never invent specific personal facts the citizen has not given or implied (real names, house numbers, registrations, reference numbers). If a required identifier is missing, ask for it.",
  "- When everything required is filled, confirm briefly and naturally what you have completed and that it is ready to submit.",
  "",
  "Record your result by calling the record_progress tool:",
  "- final_answers: use only the field keys from the mapping. Match the schema shape for each value (e.g. name is an object with firstName and lastName).",
  "- NEVER use placeholder text such as \"<UNKNOWN>\", \"N/A\", \"TBD\", or an empty string for a value you do not have. Omit that key (or that part of an object, like address line1) entirely, and ask for it instead.",
  "- reply: the message the citizen will read. Write it as a short, natural, conversational message (a sentence or two). Do NOT use bullet points, numbered lists, markdown, or literal \"\\n\" characters, and do not read a summary of every field back to them.",
  "- awaiting_input: true if you still need something from the citizen, false if the form is complete.",
].join("\n");

// Runs one agent turn over the whole conversation and returns updated answers
// plus the reply to show the user.
export async function runLlmChat(
  contract: AgentContract,
  messages: ChatMessage[],
): Promise<ChatFillResult> {
  const apiKey = env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY is missing.");

  const model = env.ANTHROPIC_MODEL ?? "claude-sonnet-5";

  // Field shapes now live in the tool schema, so the system prompt only needs the
  // field meanings (mapping) and routing rules for reasoning.
  const formContext = JSON.stringify(
    { mapping: contract.mapping, branches: contract.branches },
    null,
    2,
  );

  const system = `${SYSTEM_BRIEF}\n\nThe form you are completing:\n${formContext}`;

  // The conversation drives the turn. Fall back to a nudge if it is somehow empty.
  const conversation: ChatMessage[] =
    messages.length > 0 ? messages : [{ role: "user", content: "Please help me complete this form." }];

  // Force the tool call so the model always returns structured output.
  const progressTool = buildProgressTool(contract);
  const requestBody: Record<string, unknown> = {
    model,
    max_tokens: 1500,
    system,
    messages: conversation.map((message) => ({ role: message.role, content: message.content })),
    tools: [progressTool],
    tool_choice: { type: "tool", name: progressTool.name },
  };

  // Keep answers stable but allow a little warmth in the phrasing.
  if (!model.startsWith("claude-sonnet-5")) {
    requestBody.temperature = 0.2;
  }

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    throw new Error(`Anthropic error ${response.status}: ${await response.text()}`);
  }

  const body = (await response.json()) as {
    content?: Array<{ type: string; input?: unknown }>;
  };

  const toolCall = body.content?.find((block) => block.type === "tool_use");
  if (!toolCall) {
    throw new Error("The model did not return structured output.");
  }
  const chat = LlmChatSchema.parse(toolCall.input);

  return {
    answers: chat.final_answers,
    reply: cleanReply(chat.reply),
    awaitingInput: chat.awaiting_input ?? false,
    decision: chat.awaiting_input
      ? "Waiting on more information from the user"
      : "Completed answers from the conversation",
    rationale: `Filled ${Object.keys(chat.final_answers).length} field(s) from the conversation.`,
    model,
  };
}
