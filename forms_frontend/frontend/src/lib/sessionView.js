/** Keep terminal and final-review rendering driven by the server's state. */
export function sessionView(selectedView, state) {
  if (selectedView === "list") return "list";
  if (state?.review_required) return "review";
  if (state?.status === "COMPLETED" || (state?.review_confirmed && state?.review_ready && !state?.awaiting)) return "complete";
  return "form";
}

/** A final answer must not be followed by an older awaiting question. */
export function waitForCompletion(state, completionExpected, previousToken) {
  if (state.review_required) return false;
  return state.status === "ADVANCING"
    || (completionExpected && state.status !== "COMPLETED")
    || (previousToken && state.status !== "COMPLETED"
      && state.awaiting?.token === previousToken)
    || (state.status === "RUNNING" && !state.awaiting);
}

/** Detect a new frontend talking to the old, non-review-capable API. */
export function reviewAcknowledged(requested, acknowledged) {
  return typeof acknowledged === "boolean" && requested === acknowledged;
}
