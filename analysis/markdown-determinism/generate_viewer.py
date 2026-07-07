import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_OUTPUT_PATH = Path("viewer.html")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a standalone HTML viewer for saved experiment runs."
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help="Directory containing run folders. Defaults to runs/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="HTML file to create. Defaults to viewer.html.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not load {path}: {exc}")
        return None

    if not isinstance(value, dict):
        print(f"Ignoring {path}: expected a JSON object.")
        return None

    return value


def title_from_fixture_name(fixture_name: str) -> str:
    if not fixture_name:
        return "Unknown fixture"

    words = fixture_name.replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)


def fixture_name_from_manifest(manifest: dict[str, Any]) -> str:
    fixture_path = manifest.get("fixture_path")
    if not isinstance(fixture_path, str) or not fixture_path:
        return "unknown_fixture"

    return Path(fixture_path).name or fixture_path


def count_variant_occurrences(variants_data: dict[str, Any]) -> int:
    variants = variants_data.get("variants", [])
    if not isinstance(variants, list):
        return 0

    total = 0
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        count = variant.get("occurrence_count", 0)
        if isinstance(count, int):
            total += count
    return total


def count_non_valid_occurrences(variants_data: dict[str, Any]) -> int:
    categories = variants_data.get("non_valid_outcome_categories", {})
    if not isinstance(categories, dict):
        return 0

    total = 0
    for category in categories.values():
        if not isinstance(category, dict):
            continue
        count = category.get("count", 0)
        if isinstance(count, int):
            total += count
    return total


def fallback_completed_runs(variants_data: dict[str, Any]) -> int:
    return count_variant_occurrences(variants_data) + count_non_valid_occurrences(
        variants_data
    )


def build_run_record(run_path: Path) -> dict[str, Any] | None:
    variants = load_json(run_path / "variants.json")
    if variants is None:
        return None

    manifest = load_json(run_path / "manifest.json") or {}
    summary = load_json(run_path / "summary.json") or {}

    fixture_name = fixture_name_from_manifest(manifest)
    completed_runs = summary.get(
        "completed_runs",
        manifest.get("completed_runs", fallback_completed_runs(variants)),
    )
    requested_runs = summary.get(
        "requested_runs",
        manifest.get("requested_runs", completed_runs),
    )

    return {
        "id": run_path.name,
        "fixture_name": fixture_name,
        "fixture_title": title_from_fixture_name(fixture_name),
        "fixture_path": manifest.get("fixture_path"),
        "requested_runs": requested_runs,
        "completed_runs": completed_runs,
        "manifest": manifest,
        "summary": summary,
        "variants_data": variants,
    }


def load_runs(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.is_dir():
        return []

    records = []
    for run_path in runs_dir.iterdir():
        if not run_path.is_dir():
            continue

        record = build_run_record(run_path)
        if record is not None:
            records.append(record)

    return sorted(
        records,
        key=lambda run: (
            str(run["manifest"].get("started_at_utc", "")),
            str(run["id"]),
        ),
        reverse=True,
    )


def json_for_script(value: Any) -> str:
    serialised = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return serialised.replace("</", r"<\/")


CSS_CONTENT = r"""
:root {
  --bg: #0f1115;
  --panel: rgba(26, 29, 36, 0.76);
  --panel-solid: #1a1d24;
  --panel-border: rgba(255, 255, 255, 0.09);
  --text: #f0f2f5;
  --muted: #9ba1a6;
  --accent: #7480e8;
  --accent-soft: rgba(94, 106, 210, 0.17);
  --success: #3fb950;
  --warning: #d29922;
  --error: #f85149;
  --code: #0d0f12;
  --font-sans: "Inter", system-ui, sans-serif;
  --font-mono: "Fira Code", ui-monospace, monospace;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: var(--bg);
  background-image:
    radial-gradient(
      circle at 15% 50%,
      rgba(94, 106, 210, 0.08),
      transparent 25%
    ),
    radial-gradient(
      circle at 85% 30%,
      rgba(63, 185, 80, 0.05),
      transparent 25%
    );
  background-attachment: fixed;
  color: var(--text);
  font-family: var(--font-sans);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

button,
input {
  font: inherit;
}

#app {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 380px;
  min-width: 320px;
  background: var(--panel);
  backdrop-filter: blur(12px);
  border-right: 1px solid var(--panel-border);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 22px;
  border-bottom: 1px solid var(--panel-border);
}

.sidebar-header h2 {
  font-size: 1.25rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  margin-bottom: 14px;
}

.run-filter {
  width: 100%;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.22);
  color: var(--text);
  padding: 10px 12px;
  outline: none;
}

.run-filter:focus {
  border-color: rgba(116, 128, 232, 0.8);
  box-shadow: 0 0 0 3px rgba(116, 128, 232, 0.12);
}

.run-list {
  list-style: none;
  overflow-y: auto;
  padding: 12px;
  flex: 1;
}

.run-item {
  padding: 14px 15px;
  border-radius: 10px;
  cursor: pointer;
  margin-bottom: 9px;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
  border: 1px solid transparent;
}

.run-item:hover {
  background: rgba(255, 255, 255, 0.045);
}

.run-item.active {
  background: var(--accent-soft);
  border-color: rgba(116, 128, 232, 0.42);
}

.run-item-fixture {
  font-weight: 650;
  font-size: 0.98rem;
  margin-bottom: 3px;
}

.run-item-folder {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.73rem;
  overflow-wrap: anywhere;
  margin-bottom: 8px;
}

.run-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 0.77rem;
  color: var(--muted);
}

.run-item-pill {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
}

.run-item-pill.success {
  color: var(--success);
  background: rgba(63, 185, 80, 0.1);
}

.run-item-pill.error {
  color: var(--error);
  background: rgba(248, 81, 73, 0.1);
}

.sidebar-empty {
  color: var(--muted);
  padding: 18px;
}

.content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.content-header {
  padding: 28px 36px 24px;
  border-bottom: 1px solid var(--panel-border);
  background: rgba(15, 17, 21, 0.65);
  backdrop-filter: blur(12px);
  z-index: 10;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.header-info {
  min-width: 0;
}

.header-eyebrow {
  color: var(--accent);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.header-info h1 {
  font-size: 1.9rem;
  font-weight: 720;
  letter-spacing: -0.03em;
  margin-bottom: 5px;
}

.subtitle {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  overflow-wrap: anywhere;
}

.header-stats {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 9px;
}

.stat-badge {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  padding: 7px 11px;
  border-radius: 999px;
  font-size: 0.8rem;
  white-space: nowrap;
}

.stat-badge .value {
  color: #fff;
  font-weight: 650;
  margin-left: 4px;
}

.stat-badge.success .value {
  color: var(--success);
}

.stat-badge.error .value {
  color: var(--error);
}

.run-details {
  margin-top: 19px;
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 10px;
}

.detail {
  min-width: 0;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 9px 11px;
}

.detail-label {
  color: var(--muted);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 2px;
}

.detail-value {
  color: var(--text);
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}

.detail-value.mono {
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.variants-container {
  flex: 1;
  overflow-y: auto;
  padding: 30px 36px 42px;
  scroll-behavior: smooth;
}

.section-heading {
  font-size: 1rem;
  font-weight: 650;
  margin-bottom: 15px;
}

.outcome-panel {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 22px;
}

.outcome-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(135px, 1fr));
  gap: 10px;
}

.outcome-metric {
  background: rgba(0, 0, 0, 0.16);
  border-radius: 8px;
  padding: 10px 12px;
}

.outcome-label {
  color: var(--muted);
  font-size: 0.76rem;
  margin-bottom: 2px;
}

.outcome-value {
  font-size: 1.08rem;
  font-weight: 680;
}

.outcome-subvalue {
  color: var(--muted);
  font-size: 0.72rem;
  margin-top: 2px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 260px;
  color: var(--muted);
}

.variant-card {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  padding: 22px;
  margin-bottom: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}

.variant-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 18px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--panel-border);
}

.variant-title-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.variant-title {
  font-size: 1.15rem;
  font-weight: 650;
}

.status-badge {
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.045em;
}

.status-expected {
  background: rgba(63, 185, 80, 0.13);
  color: var(--success);
  border: 1px solid rgba(63, 185, 80, 0.28);
}

.status-accepted {
  background: rgba(210, 153, 34, 0.13);
  color: var(--warning);
  border: 1px solid rgba(210, 153, 34, 0.28);
}

.status-unexpected {
  background: rgba(248, 81, 73, 0.13);
  color: var(--error);
  border: 1px solid rgba(248, 81, 73, 0.28);
}

.variant-stats {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 16px;
  color: var(--muted);
  font-size: 0.82rem;
}

.variant-stats strong {
  color: var(--text);
}

.section-title {
  color: var(--muted);
  font-size: 0.76rem;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.055em;
  margin-bottom: 10px;
  margin-top: 20px;
}

.diff-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin-bottom: 20px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--panel-border);
}

.diff-table th,
.diff-table td {
  padding: 11px 13px;
  text-align: left;
  vertical-align: top;
  font-size: 0.8rem;
  border-bottom: 1px solid var(--panel-border);
}

.diff-table th {
  background: rgba(255, 255, 255, 0.03);
  color: var(--muted);
  font-weight: 550;
}

.diff-table tr:last-child td {
  border-bottom: none;
}

.diff-table td {
  background: rgba(0, 0, 0, 0.18);
  font-family: var(--font-mono);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.diff-path {
  color: #8a96fc;
}

.diff-expected {
  color: var(--success);
}

.diff-actual {
  color: var(--error);
}

.code-container {
  background: var(--code);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 15px;
  overflow-x: auto;
}

pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  color: #e2e8f0;
}

.json-key {
  color: #8a96fc;
}

.json-string {
  color: #56d364;
}

.json-number {
  color: #f8c055;
}

.json-boolean {
  color: #ff7b72;
}

.non-valid-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.non-valid-item {
  padding: 6px 9px;
  border-radius: 7px;
  background: rgba(248, 81, 73, 0.09);
  color: var(--error);
  font-size: 0.78rem;
}

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.11);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

@media (max-width: 1050px) {
  .sidebar {
    width: 320px;
  }

  .run-details,
  .outcome-grid {
    grid-template-columns: repeat(2, minmax(140px, 1fr));
  }

  .header-top,
  .variant-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-stats,
  .variant-stats {
    justify-content: flex-start;
  }
}
"""

JS_CONTENT = r"""
function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function highlightJSON(jsonString) {
  if (!jsonString) {
    return "";
  }

  const escaped = String(jsonString)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  const tokenPattern = new RegExp(
    '("(\\\\u[a-zA-Z0-9]{4}|\\\\[^u]|[^\\\\"])*"(\\s*:)?|' +
      "\\b(true|false|null)\\b|" +
      "-?\\d+(?:\\.\\d*)?(?:[eE][+\\-]?\\d+)?)",
    "g",
  );

  return escaped.replace(tokenPattern, (match) => {
    let className = "json-number";

    if (/^"/.test(match)) {
      className = /:$/.test(match) ? "json-key" : "json-string";
    } else if (/true|false|null/.test(match)) {
      className = "json-boolean";
    }

    return `<span class="${className}">${match}</span>`;
  });
}

function integer(value, fallback = 0) {
  return Number.isInteger(value) ? value : fallback;
}

function number(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatCount(value) {
  return integer(value).toLocaleString();
}

function formatPercent(rate) {
  const numericRate = number(rate);
  if (numericRate === null) {
    return "—";
  }
  return `${(numericRate * 100).toFixed(2)}%`;
}

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "UTC",
  }).format(parsed) + " UTC";
}

function formatDuration(startValue, finishValue) {
  if (!startValue || !finishValue) {
    return "—";
  }

  const start = new Date(startValue);
  const finish = new Date(finishValue);
  const seconds = (finish.getTime() - start.getTime()) / 1000;

  if (!Number.isFinite(seconds) || seconds < 0) {
    return "—";
  }

  if (seconds < 60) {
    return `${seconds.toFixed(1)} seconds`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return `${minutes}m ${remainder}s`;
}

function formatModel(value) {
  if (!value) {
    return "—";
  }

  const parts = String(value).split("/");
  return parts.at(-1) || String(value);
}

function formatValue(value) {
  if (value === undefined) {
    return "N/A";
  }

  if (typeof value === "string") {
    return value;
  }

  return JSON.stringify(value, null, 2);
}

function variantCount(run) {
  const variants = run.variants_data?.variants;
  return Array.isArray(variants) ? variants.length : 0;
}

function statusClass(run) {
  const summary = run.summary || {};
  const completed = integer(run.completed_runs);
  const correct = number(summary.correct_count);

  if (correct === null) {
    return "";
  }

  if (completed > 0 && correct === completed) {
    return "success";
  }

  if (completed > 0 && correct < completed) {
    return "error";
  }

  return "";
}

function sidebarSearchText(run) {
  const manifest = run.manifest || {};
  return [
    run.fixture_name,
    run.fixture_title,
    run.fixture_path,
    run.id,
    manifest.requested_model,
    ...(manifest.providers || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

document.addEventListener("DOMContentLoaded", () => {
  const runsData = window.INJECTED_RUNS_DATA || [];
  const runList = document.getElementById("run-list");
  const runFilter = document.getElementById("run-filter");
  const runEyebrow = document.getElementById("run-eyebrow");
  const runTitle = document.getElementById("run-title");
  const runSubtitle = document.getElementById("run-subtitle");
  const headerStats = document.getElementById("header-stats");
  const runDetails = document.getElementById("run-details");
  const variantsContainer = document.getElementById("variants-container");

  if (runsData.length === 0) {
    runList.innerHTML =
      '<li class="sidebar-empty">No runs with variants.json were found.</li>';
    return;
  }

  function renderSidebar(runs) {
    runList.innerHTML = "";

    if (runs.length === 0) {
      runList.innerHTML =
        '<li class="sidebar-empty">No runs match the filter.</li>';
      return;
    }

    for (const run of runs) {
      const item = document.createElement("li");
      const completed = integer(run.completed_runs);
      const requested = integer(run.requested_runs, completed);
      const variants = variantCount(run);
      const summary = run.summary || {};
      const correctRate = formatPercent(summary.correct_rate);
      const resultClass = statusClass(run);

      item.className = "run-item";
      item.dataset.id = run.id;
      item.innerHTML = `
        <div class="run-item-fixture">
          ${escapeHTML(run.fixture_name)}
        </div>
        <div class="run-item-folder">
          ${escapeHTML(run.id)}
        </div>
        <div class="run-item-meta">
          <span class="run-item-pill">
            ${formatCount(completed)}/${formatCount(requested)} runs
          </span>
          <span class="run-item-pill">
            ${formatCount(variants)} ${variants === 1 ? "variant" : "variants"}
          </span>
          <span class="run-item-pill ${resultClass}">
            ${correctRate} correct
          </span>
        </div>
      `;
      item.addEventListener("click", () => selectRun(run.id));
      runList.appendChild(item);
    }
  }

  function detail(label, value, mono = false) {
    return `
      <div class="detail">
        <div class="detail-label">${escapeHTML(label)}</div>
        <div class="detail-value ${mono ? "mono" : ""}">
          ${escapeHTML(value)}
        </div>
      </div>
    `;
  }

  function outcomeMetric(label, value, subvalue = "") {
    return `
      <div class="outcome-metric">
        <div class="outcome-label">${escapeHTML(label)}</div>
        <div class="outcome-value">${escapeHTML(value)}</div>
        ${
          subvalue
            ? `<div class="outcome-subvalue">${escapeHTML(subvalue)}</div>`
            : ""
        }
      </div>
    `;
  }

  function renderOutcomePanel(run) {
    const summary = run.summary || {};
    const latency = summary.latency_summary || {};
    const cost = summary.cost_summary || {};
    const metrics = [
      outcomeMetric(
        "Correct",
        formatPercent(summary.correct_rate),
        `${formatCount(summary.correct_count)} responses`,
      ),
      outcomeMetric(
        "Exact expected match",
        formatPercent(summary.exact_expected_match_rate),
        `${formatCount(summary.exact_expected_match_count)} responses`,
      ),
      outcomeMetric(
        "Schema valid",
        formatPercent(summary.schema_valid_rate),
        `${formatCount(summary.schema_valid_count)} responses`,
      ),
      outcomeMetric(
        "Correct tool call",
        formatPercent(summary.exactly_one_correct_tool_call_rate),
        `${formatCount(
          summary.exactly_one_correct_tool_call_count,
        )} responses`,
      ),
      outcomeMetric(
        "Canonical variants",
        formatCount(summary.unique_canonical_valid_argument_objects),
      ),
      outcomeMetric(
        "Raw argument strings",
        formatCount(summary.unique_raw_tool_argument_strings),
      ),
      outcomeMetric(
        "Median latency",
        number(latency.median) === null
          ? "—"
          : `${latency.median.toFixed(3)}s`,
      ),
      outcomeMetric(
        "Mean estimated cost",
        number(cost.mean) === null ? "—" : cost.mean.toFixed(6),
      ),
    ];

    const categories =
      run.variants_data?.non_valid_outcome_categories || {};
    const categoryItems = Object.entries(categories)
      .filter(([, data]) => integer(data?.count) > 0)
      .map(
        ([name, data]) => `
          <span class="non-valid-item">
            ${escapeHTML(name)}: ${formatCount(data.count)}
          </span>
        `,
      )
      .join("");

    return `
      <section class="outcome-panel">
        <h2 class="section-heading">Run summary</h2>
        <div class="outcome-grid">${metrics.join("")}</div>
        ${
          categoryItems
            ? `
              <div class="section-title">Non-valid outcomes</div>
              <div class="non-valid-list">${categoryItems}</div>
            `
            : ""
        }
      </section>
    `;
  }

  function renderDiffTable(differences) {
    if (!Array.isArray(differences) || differences.length === 0) {
      return "";
    }

    const rows = differences
      .map(
        (difference) => `
          <tr>
            <td class="diff-path">
              ${escapeHTML(difference.path || "-")}
            </td>
            <td class="diff-expected">
              ${escapeHTML(formatValue(difference.expected))}
            </td>
            <td class="diff-actual">
              ${escapeHTML(formatValue(difference.actual))}
            </td>
          </tr>
        `,
      )
      .join("");

    return `
      <div class="section-title">Field differences</div>
      <table class="diff-table">
        <thead>
          <tr>
            <th>Path</th>
            <th>Expected</th>
            <th>Actual</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  function renderVariant(variant) {
    let className = "status-unexpected";
    let status = "Differs from expected";

    if (variant.exactly_matches_expected) {
      className = "status-expected";
      status = "Exact expected match";
    } else if (variant.accepted_match_to_expected) {
      className = "status-accepted";
      status = "Accepted equivalent";
    }

    const proportion = formatPercent(variant.occurrence_proportion);
    const pretty =
      variant.pretty_printed_argument_string ||
      JSON.stringify(variant.parsed_argument_object, null, 2);

    return `
      <article class="variant-card">
        <div class="variant-header">
          <div class="variant-title-group">
            <div class="variant-title">
              ${escapeHTML(variant.variant_id || "Unknown variant")}
            </div>
            <div class="status-badge ${className}">
              ${escapeHTML(status)}
            </div>
          </div>
          <div class="variant-stats">
            <div>
              Count:
              <strong>${formatCount(variant.occurrence_count)}</strong>
            </div>
            <div>
              Proportion:
              <strong>${escapeHTML(proportion)}</strong>
            </div>
            <div>
              Raw forms:
              <strong>
                ${formatCount(variant.distinct_raw_string_count)}
              </strong>
            </div>
          </div>
        </div>
        ${renderDiffTable(variant.field_level_differences_from_expected)}
        <div class="section-title">Pretty-printed arguments</div>
        <div class="code-container">
          <pre>${highlightJSON(pretty)}</pre>
        </div>
      </article>
    `;
  }

  function selectRun(runId) {
    document.querySelectorAll(".run-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.id === runId);
    });

    const run = runsData.find((candidate) => candidate.id === runId);
    if (!run) {
      return;
    }

    const manifest = run.manifest || {};
    const summary = run.summary || {};
    const variants = Array.isArray(run.variants_data?.variants)
      ? run.variants_data.variants
      : [];
    const completed = integer(run.completed_runs);
    const requested = integer(run.requested_runs, completed);
    const providers = Array.isArray(manifest.providers)
      ? manifest.providers.join(", ")
      : "";
    const returnedModels = Array.isArray(
      manifest.returned_model_identifiers,
    )
      ? manifest.returned_model_identifiers.join(", ")
      : "";

    runEyebrow.textContent = "Fixture";
    runTitle.textContent = run.fixture_name;
    runSubtitle.textContent = run.id;

    const correctCount = number(summary.correct_count);
    let correctnessClass = "";

    if (correctCount !== null && completed > 0) {
      correctnessClass =
        correctCount === completed ? "success" : "error";
    }

    headerStats.innerHTML = `
      <div class="stat-badge">
        Completed
        <span class="value">
          ${formatCount(completed)}/${formatCount(requested)}
        </span>
      </div>
      <div class="stat-badge ${correctnessClass}">
        Correct
        <span class="value">${formatPercent(summary.correct_rate)}</span>
      </div>
      <div class="stat-badge">
        Variants
        <span class="value">${formatCount(variantCount(run))}</span>
      </div>
    `;

    runDetails.innerHTML = [
      detail("Fixture path", run.fixture_path || "—", true),
      detail(
        "Requested model",
        manifest.requested_model || "—",
        true,
      ),
      detail(
        "Provider / returned model",
        [providers, returnedModels].filter(Boolean).join(" · ") || "—",
        true,
      ),
      detail("Started", formatDate(manifest.started_at_utc)),
      detail(
        "Finished",
        formatDate(manifest.finished_at_utc),
      ),
      detail(
        "Duration",
        formatDuration(
          manifest.started_at_utc,
          manifest.finished_at_utc,
        ),
      ),
      detail("Stop reason", manifest.stop_reason || "—"),
      detail(
        "Concurrency / retries",
        `${manifest.concurrency ?? "—"} / ${
          manifest.retry_configuration?.max_retries ?? "—"
        }`,
      ),
    ].join("");

    const variantsHTML = variants.length
      ? variants.map(renderVariant).join("")
      : `
        <div class="empty-state">
          No schema-valid variants were recorded for this run.
        </div>
      `;

    variantsContainer.innerHTML =
      renderOutcomePanel(run) +
      '<h2 class="section-heading">Argument variants</h2>' +
      variantsHTML;

    variantsContainer.scrollTop = 0;
  }

  renderSidebar(runsData);
  selectRun(runsData[0].id);

  runFilter.addEventListener("input", () => {
    const query = runFilter.value.trim().toLowerCase();
    const filtered = query
      ? runsData.filter((run) => sidebarSearchText(run).includes(query))
      : runsData;

    renderSidebar(filtered);

    const activeId = document.querySelector(".run-item.active")?.dataset.id;
    if (!activeId && filtered.length > 0) {
      selectRun(filtered[0].id);
    }
  });
});
"""


def build_html(runs_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0"
    />
    <title>Experiment Runs Viewer</title>
    <style>
{CSS_CONTENT}
    </style>
  </head>
  <body>
    <div id="app">
      <aside class="sidebar">
        <div class="sidebar-header">
          <h2>Experiment runs</h2>
          <input
            id="run-filter"
            class="run-filter"
            type="search"
            placeholder="Filter by fixture, run or model"
            aria-label="Filter experiment runs"
          />
        </div>
        <ul id="run-list" class="run-list">
          <li class="sidebar-empty">Loading runs…</li>
        </ul>
      </aside>

      <main class="content">
        <header class="content-header">
          <div class="header-top">
            <div class="header-info">
              <div id="run-eyebrow" class="header-eyebrow">
                Fixture
              </div>
              <h1 id="run-title">Select a run</h1>
              <p id="run-subtitle" class="subtitle">
                Choose a run from the sidebar.
              </p>
            </div>
            <div id="header-stats" class="header-stats"></div>
          </div>
          <div id="run-details" class="run-details"></div>
        </header>

        <div id="variants-container" class="variants-container">
          <div class="empty-state">No run selected.</div>
        </div>
      </main>
    </div>
    <script>
      window.INJECTED_RUNS_DATA = {runs_json};
{JS_CONTENT}
    </script>
  </body>
</html>
"""


def main() -> None:
    args = parse_args()
    runs = load_runs(args.runs_dir)
    html = build_html(json_for_script(runs))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(
        "Generated standalone report at "
        f"{args.output.resolve()} using {len(runs)} run(s)."
    )


if __name__ == "__main__":
    main()
