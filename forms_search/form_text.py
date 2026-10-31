"""Render a GOV.UK Forms export as compact, model-readable text.

The raw exports carry ids, timestamps and routing plumbing that add tokens
without telling a model what a Form is for. This keeps the user-facing
content (title, questions, hints, options, guidance, exit pages and the
"what happens next" text) in question order.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Per-field cap. Guidance on a handful of Forms runs to many KB of policy text;
# the opening paragraphs are enough to say what the Form is for.
MAX_FIELD_CHARS = 1500
MAX_OPTIONS = 20

_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "form",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "your",
    "my",
    "with",
    "request",
    "apply",
    "application",
}


def load_form(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def form_id(form: dict[str, Any]) -> str:
    return str(form["form_id"])


def form_title(form: dict[str, Any]) -> str:
    return " ".join(form["content"]["name"].split())


def source_hash(form: dict[str, Any]) -> str:
    """Stable hash of the Form content, so edits to a Form trigger regeneration."""
    canonical = json.dumps(form["content"], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _clean(text: str | None, limit: int = MAX_FIELD_CHARS) -> str:
    if not text:
        return ""
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + " … [truncated]"
    return text


def _indent(text: str, prefix: str = "   ") -> str:
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _ordered_steps(content: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(content.get("steps") or [], key=lambda s: s.get("position") or 0)


def _render_step(index: int, step: dict[str, Any]) -> str:
    data = step.get("data") or {}
    flags = [data.get("answer_type") or "unknown"]
    if data.get("is_optional"):
        flags.append("optional")
    if data.get("is_repeatable"):
        flags.append("repeatable")

    lines = []
    if heading := _clean(data.get("page_heading"), 200):
        lines.append(f"{index}. [Page heading: {heading}]")
        lines.append(
            f"   Q: {_clean(data.get('question_text'), 300)} ({', '.join(flags)})"
        )
    else:
        lines.append(
            f"{index}. Q: {_clean(data.get('question_text'), 300)} ({', '.join(flags)})"
        )

    if hint := _clean(data.get("hint_text"), 400):
        lines.append(f"   Hint: {hint}")

    options = (data.get("answer_settings") or {}).get("selection_options") or []
    if options:
        names = [str(o.get("name", "")).strip() for o in options[:MAX_OPTIONS]]
        more = (
            f" (+{len(options) - MAX_OPTIONS} more)"
            if len(options) > MAX_OPTIONS
            else ""
        )
        lines.append(f"   Options: {'; '.join(names)}{more}")

    if guidance := _clean(data.get("guidance_markdown")):
        lines.append("   Guidance:")
        lines.append(_indent(guidance, "     "))

    # Exit pages are the clearest source-backed signal of who a Form is *not* for.
    for condition in step.get("routing_conditions") or []:
        exit_heading = _clean(condition.get("exit_page_heading"), 200)
        exit_body = _clean(condition.get("exit_page_markdown"), 600)
        if exit_heading or exit_body:
            answer = condition.get("answer_value")
            lines.append(
                f"   If answer is {answer!r}, user exits the form: {exit_heading}"
            )
            if exit_body:
                lines.append(_indent(exit_body, "     "))

    return "\n".join(lines)


def render_form(form: dict[str, Any]) -> str:
    content = form["content"]
    parts = [
        f"Title: {form_title(form)}",
        f"Form ID: {form_id(form)}",
        f"Takes payment: {'yes' if content.get('payment_url') else 'no'}",
    ]
    if email := content.get("support_email"):
        parts.append(f"Support email: {email}")
    if privacy := content.get("privacy_policy_url"):
        parts.append(f"Privacy policy: {privacy}")

    steps = _ordered_steps(content)
    parts.append(f"\nQuestions ({len(steps)}):")
    parts.extend(_render_step(i, step) for i, step in enumerate(steps, start=1))

    if declaration := _clean(
        content.get("declaration_markdown") or content.get("declaration_text")
    ):
        parts.append(f"\nDeclaration:\n{declaration}")
    if next_steps := _clean(content.get("what_happens_next_markdown")):
        parts.append(f"\nWhat happens next:\n{next_steps}")

    return "\n".join(parts)


def _title_tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def similar_titles(
    target_id: str, titles: dict[str, str], limit: int = 5, threshold: float = 0.3
) -> list[str]:
    """Titles of other Forms that look similar, so the model can say what differs."""
    target = _title_tokens(titles[target_id])
    if not target:
        return []
    scored = []
    for other_id, title in titles.items():
        if other_id == target_id:
            continue
        other = _title_tokens(title)
        if not other:
            continue
        score = len(target & other) / len(target | other)
        if score >= threshold:
            scored.append((score, title))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [title for _, title in scored[:limit]]
