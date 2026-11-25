/**
 * A question is offered to the agent at most once per policy and session.
 * Refreshing Temporal's unchanged awaiting input must not restart a failed
 * automatic run (or repeatedly ask for the same confirmation proposal).
 */
export function createProposalAttemptGate() {
  let currentSession = null;
  const attempted = new Set();

  return {
    claim(sessionId, token, policy) {
      if (!sessionId || !token || policy === "manual") return false;
      if (currentSession !== sessionId) {
        currentSession = sessionId;
        attempted.clear();
      }
      const key = JSON.stringify([token, policy]);
      if (attempted.has(key)) return false;
      attempted.add(key);
      return true;
    },
    retry(sessionId, token, policy) {
      if (currentSession === sessionId) {
        attempted.delete(JSON.stringify([token, policy]));
      }
    },
  };
}
