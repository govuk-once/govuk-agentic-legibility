// Client-side store holding the run log for the current form.
//
// The agent runs on the main page, but the log is viewed on /log, so the log
// has to outlive a navigation. It lives in a runes store and is mirrored to
// sessionStorage so a refresh of /log (or landing there directly) still shows
// the latest run. A new form clears it.

import { appendTurn, type RunLog, type TurnInput } from "$lib/run-log";

const STORAGE_KEY = "agentic-forms-run-log";

// Reads any persisted log. Guarded for SSR, where sessionStorage is absent.
function load(): RunLog | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as RunLog) : null;
  } catch {
    return null;
  }
}

// A single reactive holder. Components read `runLogStore.log`; mutating this
// property is what triggers re-render.
export const runLogStore = $state<{ log: RunLog | null }>({ log: load() });

function persist() {
  if (typeof sessionStorage === "undefined") return;
  try {
    if (runLogStore.log) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(runLogStore.log));
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Ignore storage quota / private-mode errors; the in-memory log still works.
  }
}

// Records one agent turn into the log.
export function recordTurn(input: TurnInput) {
  runLogStore.log = appendTurn(runLogStore.log, input);
  persist();
}

// Clears the log. Call when a new form is loaded or the form is reset.
export function resetRunLog() {
  runLogStore.log = null;
  persist();
}
