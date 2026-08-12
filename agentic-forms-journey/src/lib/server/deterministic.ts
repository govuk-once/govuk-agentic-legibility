import type { GovForm } from "$lib/schemas";
import type { AgentContract, FillResult, MappingRow } from "./engine-types";

// Returns deterministic placeholder values so baseline runs stay repeatable.
function deterministicValue(page: GovForm["pages"][number], row: MappingRow) {
  switch (page.answerType) {
    case "text":
      return { value: "Deterministic placeholder text.", why: "Filled with baseline text." };
    case "number":
      return { value: 1, why: "Filled with baseline number." };
    case "date":
      return { value: "2026-07-01", why: "Filled with baseline date." };
    case "email":
      return { value: "citizen@example.com", why: "Filled with baseline email address." };
    case "address":
      return {
        value: { line1: "1 Example Street", town: "Leeds", postcode: "LS1 1AA" },
        why: "Filled with baseline postal address.",
      };
    case "name":
      return {
        value: { firstName: "Alex", lastName: "Taylor" },
        why: "Filled with baseline person name.",
      };
    case "selection":
      if (page.answerSettings?.selectionType === "checkbox") {
        return {
          value: row.options?.length ? [row.options[0]] : [],
          why: row.options?.length
            ? "Filled with first checkbox option."
            : "No options were available.",
        };
      }
      return {
        value: row.options?.[0] ?? "",
        why: row.options?.length ? "Filled with first option." : "No options were available.",
      };
    case "file":
      return {
        value: "requires-human-upload",
        why: "File answers cannot be auto-filled in this demo.",
      };
    default:
      return { value: "placeholder", why: "Filled with fallback placeholder text." };
  }
}

// Builds deterministic answers for required keys only.
export function runDeterministicFill(contract: AgentContract, form: GovForm): FillResult {
  const pageById = new Map(form.pages.map((page) => [page.id, page]));
  const answers: Record<string, unknown> = {};

  // Only fill keys that are currently mandatory at top level.
  // Conditionally skipped keys are handled by schema conditionals at validation time.
  for (const row of contract.mapping) {
    if (!row.required) continue;
    const page = pageById.get(row.pageId);
    if (!page) continue;
    const sample = deterministicValue(page, row);
    answers[row.key] = sample.value;
  }

  return {
    answers,
    decision: "Generated deterministic answers for required fields",
    rationale: `Filled ${Object.keys(answers).length} required key(s) with fixed placeholders.`,
  };
}
