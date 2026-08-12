import Ajv from "ajv";
import addFormats from "ajv-formats";
import type { JsonSchema, ValidationResult } from "./engine-types";

const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);

// Validates answers against generated JSON Schema using Ajv.
// referenced and brought forward from original poc https://github.com/MaxwellRiess/Agentic-forms-poc
export function validateAnswers(schema: JsonSchema, answers: Record<string, unknown>): ValidationResult {
  const validate = ajv.compile(schema);
  const valid = validate(answers) as boolean;
  if (valid) return { valid: true, errors: [] };

  return {
    valid: false,
    errors: (validate.errors ?? []).map((error) => {
      // Convert JSON Pointer paths to dot paths for easier UI reading.
      const path = error.instancePath.replace(/^\//, "").replace(/\//g, ".");
      const field =
        path ||
        ((error.params as { missingProperty?: string }).missingProperty ?? "(root)");
      return { field, message: error.message ?? "is invalid" };
    }),
  };
}

// Pulls missing required fields from Ajv errors for clear reporting.
export function getMissingRequiredFields(errors: ValidationResult["errors"]): string[] {
  // Ajv marks missing required fields using message text and field name.
  // We extract and de-duplicate those names for comparison metrics.
  const missing = errors
    .filter((error) => error.message.includes("required property"))
    .map((error) => error.field)
    .filter((field) => field !== "(root)");
  return [...new Set(missing)];
}
