/** Overall accepted journey inputs, not just answers from this auto pass. */
export function cumulativeAnsweredCount(current, event) {
  if (Number.isInteger(event.answered_count) && event.answered_count >= 0) {
    // A late SSE event from an older pass cannot roll the progress bar back.
    return Math.max(current, event.answered_count);
  }
  return event.type === 'step' ? current + 1 : current;
}
