"""Conservative GOV.UK Forms -> SFSM/0.2 compiler.

SFSM is deliberately the output contract: progression is represented by ``next``
references and native ``choice`` predicates, never by a client or an agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.model import SFSMDefinition


class UnsupportedForm(ValueError):
    """The export uses a feature this vertical slice cannot preserve safely."""


@dataclass(frozen=True)
class Question:
    id: str
    data: dict[str, Any]
    next_id: str | None
    routing: list[dict[str, Any]]
    position: int


def _unsupported(where: str, reason: str) -> None:
    raise UnsupportedForm(f"{where}: {reason}")


def normalise_form(export: dict[str, Any]) -> tuple[dict[str, Any], list[Question]]:
    """Both ``question_page`` and ``question`` have the same core semantics."""
    content = export.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("steps"), list):
        _unsupported("form", "expected content.steps array")
    if not str(content.get("form_id") or export.get("form_id") or "").isdigit():
        _unsupported("form", "missing or non-numeric form_id")
    if content.get("payment_url"):
        _unsupported("form", "payment integration is not implemented")
    steps: list[Question] = []
    seen: set[str] = set()
    for item in content["steps"]:
        where = f"step {item.get('id', '<missing>')}"
        if item.get("type") not in ("question", "question_page"):
            _unsupported(where, f"unsupported step type {item.get('type')!r}")
        if item.get("exit_pages"):
            _unsupported(where, "exit_pages are not implemented")
        data = item.get("data")
        if not isinstance(data, dict):
            _unsupported(where, "missing data")
        if not isinstance(data.get("is_optional", False), bool) or not isinstance(data.get("is_repeatable", False), bool):
            _unsupported(where, "is_optional and is_repeatable must be booleans")
        if data.get("is_repeatable"):
            _unsupported(where, "repeatable question")
        sid = item.get("id")
        if not isinstance(sid, str) or not sid or sid in seen or "__" in sid:
            _unsupported(where, "missing, duplicate or reserved step ID")
        seen.add(sid)
        if not isinstance(data.get("question_text"), str) or not data["question_text"].strip():
            _unsupported(where, "missing question_text")
        routing = item.get("routing_conditions") or []
        if not isinstance(routing, list):
            _unsupported(where, "routing_conditions must be an array")
        steps.append(Question(sid, data, item.get("next_step_id"), routing, item.get("position", 0)))
    if not steps:
        _unsupported("form", "no supported questions")
    ids = {item.id for item in steps}
    start = content.get("start_page") or steps[0].id
    if start not in ids:
        _unsupported("form", f"unknown start_page {start!r}")
    for item in steps:
        if item.next_id is not None and item.next_id not in ids:
            _unsupported(f"step {item.id}", f"unknown next_step_id {item.next_id!r}")
    return content, steps


def _fields(question: Question) -> list[tuple[str, str, bool]]:
    """(field suffix, human label, required) within a Forms question."""
    answer_type = question.data.get("answer_type")
    settings = question.data.get("answer_settings") or {}
    required = not question.data.get("is_optional", False)
    if answer_type == "name":
        # Capturing a name needs only a string input. Preserve the original
        # full-name / component / title settings in presentation metadata so a
        # Forms-aware frontend can choose the appropriate controls later.
        return [("", "", required)]
    if answer_type == "address":
        address_types = settings.get("input_type", {})
        if not isinstance(address_types, dict) or address_types.get("uk_address") not in ("true", True) or address_types.get("international_address") not in ("false", False, None):
            _unsupported(question.id, "only UK-only addresses are supported")
        return [("address_line_1", "Address line 1", required),
                ("address_line_2", "Address line 2", False),
                ("town_or_city", "Town or city", required),
                ("postcode", "Postcode", required)]
    if answer_type in ("text", "national_insurance_number", "email", "date", "number", "organisation_name", "selection"):
        if answer_type == "selection":
            options = settings.get("selection_options")
            if not isinstance(options, list) or not options:
                _unsupported(question.id, "selection has no options")
            if settings.get("only_one_option") not in ("true", "false", True, False):
                _unsupported(question.id, "unrecognised only_one_option")
        return [("", "", required)]
    _unsupported(question.id, f"unsupported answer_type {answer_type!r}")


def _presentation(question: Question, *, suffix: str = "", label: str = "") -> dict[str, Any]:
    data = question.data
    return {
        "source": "govuk_forms",
        "step_id": question.id,
        "position": question.position,
        "question_text": data["question_text"],
        "page_heading": data.get("page_heading"),
        "hint_text": data.get("hint_text"),
        "guidance_markdown": data.get("guidance_markdown"),
        "answer_type": data.get("answer_type"),
        "answer_settings": data.get("answer_settings"),
        "is_optional": bool(data.get("is_optional", False)),
        "field": suffix or None,
        "field_label": label or None,
        "required": next(req for field, _, req in _fields(question) if field == suffix),
        "is_first_field": _fields(question)[0][0] == suffix,
    }


def _schema(question: Question, *, required: bool, suffix: str) -> dict[str, Any]:
    data = question.data
    answer_type = data.get("answer_type")
    settings = data.get("answer_settings") or {}
    schema: dict[str, Any] = {"kind": "string"}
    if answer_type == "selection":
        only_one = settings["only_one_option"] in ("true", True)
        schema["kind"] = "select_one" if only_one else "select_many"
        options = []
        for opt in settings["selection_options"]:
            if not isinstance(opt, dict) or not isinstance(opt.get("value"), str) or not isinstance(opt.get("name"), str):
                _unsupported(question.id, "selection option must have string name and value")
            if any(prior["value"] == opt["value"] for prior in options):
                _unsupported(question.id, "duplicate selection value")
            if opt.get("is_other") or opt.get("requires_text"):
                _unsupported(question.id, "free-text selection option is not implemented")
            options.append({"value": opt["value"], "label": opt["name"]})
        # The interpreter currently validates select_one against its option list
        # even when allow_skip=True. Use a real, distinct skip option instead.
        if not required and only_one:
            if any(opt["value"] == "__forms_skip__" for opt in options):
                _unsupported(question.id, "reserved optional selection value")
            options.append({"value": "__forms_skip__", "label": "Skip this question"})
        schema["options"] = options
    if not required:
        schema["allow_skip"] = True
        if schema["kind"] == "string":
            schema["default"] = ""
    schema["presentation"] = _presentation(question, suffix=suffix,
        label=dict((name, label) for name, label, _ in _fields(question)).get(suffix, ""))
    return schema


def compile_form(export: dict[str, Any]) -> dict[str, Any]:
    """Return a definition validated by the *actual* SFSMDefinition model."""
    content, questions = normalise_form(export)
    ids = {question.id for question in questions}
    states: dict[str, dict[str, Any]] = {}
    for question in questions:
        fields = _fields(question)
        if question.routing and len(fields) != 1:
            _unsupported(question.id, "routing on compound input is not implemented")
        after = f"{question.id}__route" if question.routing else (question.next_id or "end_form")
        for idx, (suffix, label, required) in enumerate(fields):
            sid = question.id if idx == 0 else f"{question.id}__{suffix}"
            next_state = (f"{question.id}__{fields[idx + 1][0]}" if idx < len(fields) - 1 else after)
            prompt = question.data["question_text"] if idx == 0 else label
            if idx == 0 and label:
                prompt += f" — {label}"
            states[sid] = {
                "type": "input", "prompt": prompt,
                "schema": _schema(question, required=required, suffix=suffix),
                "assign": f"answers.{question.id}" + (f".{suffix}" if suffix else ""),
                "next": next_state,
            }
        if question.routing:
            rules = []
            for condition in question.routing:
                if not isinstance(condition, dict):
                    _unsupported(question.id, "routing condition must be an object")
                if condition.get("routing_page_id") not in (None, question.id) or condition.get("check_page_id") not in (None, question.id):
                    _unsupported(question.id, "cross-page routing is not supported")
                if condition.get("exit_page_id") is not None or condition.get("exit_page_markdown") or condition.get("exit_page_heading"):
                    _unsupported(question.id, "exit-page routing is not implemented")
                if condition.get("validation_errors"):
                    _unsupported(question.id, "routing condition contains validation errors")
                answer = condition.get("answer_value")
                if not isinstance(answer, str):
                    _unsupported(question.id, "routing requires a string answer_value")
                target = condition.get("goto_page_id")
                if condition.get("skip_to_end"):
                    if target is not None:
                        _unsupported(question.id, "ambiguous skip_to_end and goto_page_id")
                    target = "end_form"
                if target is None or (target != "end_form" and target not in ids):
                    _unsupported(question.id, f"invalid routing target {target!r}")
                kind = states[question.id]["schema"]["kind"]
                if kind not in ("select_one", "select_many"):
                    _unsupported(question.id, "routing on non-selection input not supported")
                values = {o["value"] for o in states[question.id]["schema"]["options"]}
                if answer not in values:
                    _unsupported(question.id, f"routing answer_value {answer!r} missing from selection")
                rules.append({"when": {"op": "contains" if kind == "select_many" else "eq",
                                       "path": f"answers.{question.id}", "value": answer},
                              "next": target})
            states[f"{question.id}__route"] = {"type": "choice", "rules": rules,
                                               "default": question.next_id or "end_form"}
    if "end_form" in states or any(q.id == "end_form" for q in questions):
        _unsupported("form", "reserved end_form state ID")
    states["end_form"] = {"type": "end", "status": "success", "outcome": "form_answers_collected"}
    for sid, state in states.items():
        for target in ([state["next"]] if state["type"] == "input" else
                       [r["next"] for r in state["rules"]] + [state["default"]] if state["type"] == "choice" else []):
            if target not in states:
                _unsupported(sid, f"generated transition to missing state {target!r}")
    definition = {
        "schema": "sfsm/0.2", "id": f"govuk.forms.{content.get('form_id', export.get('form_id'))}",
        "workflow_id": int(content.get("form_id") or export["form_id"]),
        "version": "0.1.0", "entry": "main", "executor": {},
        "defaults": {"forms": {"form_id": content.get("form_id", export.get("form_id")),
                              "name": content.get("name"), "start_page": content.get("start_page"),
                              "form_slug": content.get("form_slug"),
                              "support_url": content.get("support_url"),
                              "support_email": content.get("support_email"),
                              "support_phone": content.get("support_phone"),
                              "support_url_text": content.get("support_url_text"),
                              "language": content.get("language"),
                              "what_happens_next_markdown": content.get("what_happens_next_markdown"),
                              "privacy_policy_url": content.get("privacy_policy_url"),
                              "declaration_markdown": content.get("declaration_markdown"),
                              "submission_type": content.get("submission_type"),
                              "preview_only": True}},
        "processes": {"main": {"start": content.get("start_page") or questions[0].id,
                                "vars": {"answers": {}}, "states": states}},
    }
    SFSMDefinition.model_validate(definition)
    return definition
