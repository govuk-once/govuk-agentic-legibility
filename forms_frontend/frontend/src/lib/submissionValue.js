/** Convert a rendered Forms control into the native SFSM input value.
 *  Empty optional values are distinct from "0" and false, and selection
 *  skips must use their explicit compiled-schema option (not the empty string).
 */
export function submissionValue(value, schema, isOptional) {
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
    if (schema?.kind === "select_many") return { value: [] };
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
