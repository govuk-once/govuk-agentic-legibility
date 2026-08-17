import type { GovForm } from "$lib/schemas";
import type { AgentContract, JsonSchema, MappingRow } from "./engine-types";

// referenced and brought forward from original poc https://github.com/MaxwellRiess/Agentic-forms-poc
function slugify(text: string): string {
  const cleaned = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned || "answer";
}

// Converts each GOV Forms answer type into an equivalent JSON Schema fragment.
// referenced and brought forward from original poc https://github.com/MaxwellRiess/Agentic-forms-poc
function answerFragment(page: GovForm["pages"][number]): JsonSchema {
  switch (page.answerType) {
    case "text":
      return {
        type: "string",
        maxLength: page.answerSettings?.inputType === "long_text" ? 5000 : 500,
      };
    case "number":
      return { type: "number" };
    case "date":
      return { type: "string", format: "date" };
    case "email":
      return { type: "string", format: "email" };
    case "address":
      return {
        type: "object",
        properties: {
          line1: { type: "string" },
          line2: { type: "string" },
          town: { type: "string" },
          postcode: { type: "string" },
        },
        required: ["line1", "town", "postcode"],
        additionalProperties: false,
      };
    case "name": {
      const props: Record<string, unknown> = {
        firstName: { type: "string" },
        lastName: { type: "string" },
      };
      if (page.answerSettings?.includeTitle) props.title = { type: "string" };
      return {
        type: "object",
        properties: props,
        required: ["firstName", "lastName"],
        additionalProperties: false,
      };
    }
    case "selection": {
      const options = page.answerSettings?.selectionOptions?.map((option) => option.name) ?? [];
      if (page.answerSettings?.selectionType === "checkbox") {
        return {
          type: "array",
          items: { type: "string", enum: options },
          uniqueItems: true,
        };
      }
      return { type: "string", enum: options };
    }
    default:
      return { type: "string" };
  }
}

// Builds mapping, routing notes, and one generated answer schema for the form.
// referenced and brought forward from original poc https://github.com/MaxwellRiess/Agentic-forms-poc
export function buildAgentContract(form: GovForm): AgentContract {
  // Normalise page order first so every later step follows the journey order.
  // If position is missing, use array index so we still get deterministic ordering.
  const ordered = form.pages
    .map((page, index) => ({ page, order: page.position ?? index + 1 }))
    .sort((left, right) => left.order - right.order);

  // Build one stable key per question for agent answer payloads.
  const seen = new Map<string, number>();
  const mapping: MappingRow[] = ordered.map(({ page }) => {
    let key = slugify(page.questionText);
    const count = seen.get(key) ?? 0;
    seen.set(key, count + 1);
    if (count > 0) key = `${key}_${count + 1}`;

    return {
      pageId: page.id,
      key,
      questionText: page.questionText,
      answerType: page.answerType,
      required: !page.isOptional,
      options: page.answerSettings?.selectionOptions?.map((option) => option.name),
    };
  });

  // Build lookup maps used by routing and schema assembly.
  const mappingByPageId = new Map(mapping.map((row) => [row.pageId, row]));
  const orderByPageId = new Map(ordered.map((item) => [item.page.id, item.order]));
  const questionById = new Map(ordered.map((item) => [item.page.id, item.page.questionText]));

  type SkipCondition = { questionKey: string; questionText: string; value: string };
  const skips = new Map<string, SkipCondition[]>();
  const branches: string[] = [];
  const branchRules: AgentContract["branchRules"] = [];

  const addSkip = (pageId: string, condition: SkipCondition) => {
    const existing = skips.get(pageId) ?? [];
    existing.push(condition);
    skips.set(pageId, existing);
  };

  // Analyse each routing rule and collect skipped pages for conditional schema logic.
  for (const { page: question, order } of ordered) {
    if (!question.routing?.length) continue;
    const questionRow = mappingByPageId.get(question.id);
    if (!questionRow) continue;

    for (const rule of question.routing) {
      let upperBound = Number.POSITIVE_INFINITY;
      let targetLabel = "end of form";

      if (rule.goToPageId !== "CHECK_ANSWERS") {
        const targetOrder = orderByPageId.get(rule.goToPageId);
        if (!targetOrder) continue;
        upperBound = targetOrder;
        targetLabel = questionById.get(rule.goToPageId) ?? rule.goToPageId;
      }

      // Collect every question that would be skipped by this jump.
      const skippedQuestionTexts: string[] = [];
      for (const candidate of ordered) {
        if (candidate.order > order && candidate.order < upperBound) {
          skippedQuestionTexts.push(candidate.page.questionText);
          addSkip(candidate.page.id, {
            questionKey: questionRow.key,
            questionText: question.questionText,
            value: rule.answerValue,
          });
        }
      }

      branches.push(
        `${question.questionText}: if "${rule.answerValue}" then jump to ${targetLabel}`,
      );
      branchRules.push({
        questionKey: questionRow.key,
        questionText: question.questionText,
        answerValue: rule.answerValue,
        jumpTo: targetLabel,
        skippedQuestionTexts: [...new Set(skippedQuestionTexts)],
      });
    }
  }

  const pageById = new Map(form.pages.map((page) => [page.id, page]));
  const properties: Record<string, unknown> = {};
  const required: string[] = [];
  const conditionals: unknown[] = [];

  // Build one JSON Schema property per mapped question key.
  for (const row of mapping) {
    const page = pageById.get(row.pageId);
    if (!page) continue;
    properties[row.key] = answerFragment(page);
  }

  // Convert skip rules into JSON Schema if/then/else conditionals.
  for (const [pageId, conditions] of skips) {
    const row = mappingByPageId.get(pageId);
    const page = pageById.get(pageId);
    if (!row || !page) continue;

    row.required = false;
    row.appliesWhen = `Omit when ${conditions
      .map((condition) => `"${condition.questionText}" is "${condition.value}"`)
      .join(" or ")}`;

    const skipIf = {
      anyOf: conditions.map((condition) => ({
        properties: { [condition.questionKey]: { const: condition.value } },
        required: [condition.questionKey],
      })),
    };

    // If rule matches, key must be omitted.
    // If rule does not match and page is mandatory, key is required.
    const block: Record<string, unknown> = {
      if: skipIf,
      then: { not: { required: [row.key] } },
    };

    if (!page.isOptional) {
      block.else = { required: [row.key] };
    }

    conditionals.push(block);
  }

  // Build the required list after conditional adjustments.
  for (const row of mapping) {
    if (row.required) required.push(row.key);
  }

  const schema: JsonSchema = {
    type: "object",
    properties,
    required,
    additionalProperties: false,
  };

  if (conditionals.length > 0) {
    schema.allOf = conditionals;
  }

  return { schema, mapping, branches, branchRules };
}
