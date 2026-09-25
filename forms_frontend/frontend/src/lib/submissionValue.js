/** Convert a rendered Forms control into the native SFSM input value.
 *  Empty optional values are distinct from "0" and false, and selection
 *  skips must use their explicit compiled-schema option (not the empty string).
 */
export function submissionValue(value, schema, isOptional) {
  if (schema?.kind === "select_many") {
    // Temporal's select_many validator requires an array, never the scalar
    // value returned by a radio control. Empty required selections must also
    // be rejected before reaching Temporal.
    if (value === null || value === undefined || value === "") {
      return isOptional ? { value: [] } : { error: "Select at least one option" };
    }
    if (!Array.isArray(value)) {
      return { error: "Select one or more options" };
    }
    if (!isOptional && value.length === 0) {
      return { error: "Select at least one option" };
    }
    return { value };
  }
  const missing = value === null || value === undefined || value === "";
  if (missing && !isOptional) {
    return { error: "This field is required" };
  }
  if (missing) {
    if (schema?.kind === "file_ref") return { value: null };
    if (schema?.kind === "select_one") {
      const skip = schema.options?.find((item) => item.value === "__forms_skip__");
      if (skip) return { value: skip.value };
    }
    return { value: schema?.default ?? "" };
  }
  if (schema?.kind === "boolean") {
    if (value === "true") return { value: true };
    if (value === "false") return { value: false };
  }
  // GOV.UK Forms numbers are string SFSM inputs; the renderer may supply 0.
  if (schema?.kind === "string" && typeof value === "number") {
    return { value: String(value) };
  }
  return { value };
}
