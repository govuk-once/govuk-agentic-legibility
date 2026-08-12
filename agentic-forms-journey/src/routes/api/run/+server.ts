import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { GovFormSchema } from "$lib/schemas";
import type { ChatMessage } from "$lib/server/engine-types";
import { runComparison } from "$lib/server/compare";

// Runs one agent turn: parse the uploaded form, replay the conversation, and
// return the updated comparison plus the agent's reply.
export const POST: RequestHandler = async ({ request }) => {
  try {
    const payload = (await request.json()) as {
      formJson?: string;
      messages?: ChatMessage[];
    };

    if (!payload.formJson) {
      return json({ error: "No form has been uploaded yet." }, { status: 400 });
    }

    const raw = JSON.parse(payload.formJson);
    const form = GovFormSchema.parse(raw);

    const messages = Array.isArray(payload.messages) ? payload.messages : [];
    const result = await runComparison(form, messages);

    return json({ result });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return json({ error: message }, { status: 400 });
  }
};
