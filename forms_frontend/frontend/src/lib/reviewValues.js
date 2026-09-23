/** Presentation only. Accepted values and routing always come from Temporal. */
export function formatReviewValue(answer) {
  const value = answer.value;
  if (value === null || value === undefined || value === "" || value === "__forms_skip__"
    || (Array.isArray(value) && value.length === 0)) return "Not answered";
  if (value === true || value === false) return value ? "Yes" : "No";
  if (answer.schema.kind === "file_ref" && typeof value === "object") {
    return `Uploaded file (${value.bytes ?? "?"} bytes)`;
  }
  if (answer.schema.kind === "select_one" || answer.schema.kind === "select_many") {
    const options = answer.schema.options ?? [];
    const label = (v) => options.find((o) => o.value === v)?.label ?? v;
    return Array.isArray(value) ? value.map(label).join(", ") : label(String(value));
  }
  return Array.isArray(value) ? value.join(", ") : String(value);
}

export function initialReviewDraft(answer) {
  if (answer.schema.kind === "boolean") {
    return answer.value === true ? "true" : answer.value === false ? "false" : "";
  }
  if (Array.isArray(answer.value)) return [...answer.value];
  return answer.value === null || answer.value === undefined ? "" : String(answer.value);
}
