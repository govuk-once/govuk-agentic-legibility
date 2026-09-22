"""GOV.UK Forms -> SFSM/0.2 journey compiler.

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
        # Older exports may omit these flags or explicitly store null. Both mean
        # the Forms default (false); never interpret a non-boolean string as truthy.
        data = dict(data)
        for flag in ("is_optional", "is_repeatable"):
            value = data.get(flag)
            if value is None:
                data[flag] = False
            elif not isinstance(value, bool):
                _unsupported(where, f"{flag} must be a boolean or null")
        if data["is_repeatable"]:
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


def _selection_options(question: Question) -> tuple[bool | None, list[dict[str, str]]]:
    """Parse actual Forms selection settings without guessing cardinality."""
    settings = question.data.get("answer_settings")
    if not isinstance(settings, dict):
        return None, []
    raw_only_one = settings.get("only_one_option")
    if raw_only_one in (True, "true"):
        only_one = True
    elif raw_only_one in (False, "false"):
        only_one = False
    else:
        only_one = None
    raw_options = settings.get("selection_options")
    if not isinstance(raw_options, list) or not raw_options:
        return only_one, []
    options = []
    for opt in raw_options:
        if (not isinstance(opt, dict)
                or not isinstance(opt.get("value"), str)
                or not isinstance(opt.get("name"), str)
                or opt.get("is_other") or opt.get("requires_text")
                or any(prev["value"] == opt.get("value") for prev in options)):
            return only_one, []
        options.append({"value": opt["value"], "label": opt["name"]})
    return only_one, options


def _boolean_choices(question: Question, *, required: bool) -> bool:
    """Use a native boolean *only* for unambiguous routed Yes/No selections.

    Unrouted questions, even if their wording sounds binary, remain strings or
    ordinary selections. Optional selections retain an explicit skip option.
    """
    if (question.data.get("answer_type") != "selection"
            or not question.routing or not required):
        return False
    only_one, options = _selection_options(question)
    values = {option["value"].strip().lower() for option in options}
    return only_one is True and values in ({"yes", "no"}, {"true", "false"})


def _presentation(question: Question) -> dict[str, Any]:
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
        "is_optional": data["is_optional"],
        # Retain the existing renderer's metadata contract even though the
        # process graph now has exactly one input state per Forms question.
        "field": None,
        "field_label": None,
        "required": not data["is_optional"],
        "is_first_field": True,
    }


def _schema(question: Question) -> dict[str, Any]:
    answer_type = question.data.get("answer_type")
    required = not question.data["is_optional"]
    schema: dict[str, Any] = {"kind": "string"}
    if answer_type == "file":
        # SFSM and the Temporal interpreter already accept a file *reference*.
        # Producing that reference is a separate client/upload integration.
        # The interpreter cannot currently accept a skipped file_ref value.
        if not required:
            _unsupported(question.id, "optional file_ref skip is not implemented")
        schema = {"kind": "file_ref"}
    elif answer_type == "selection":
        only_one, options = _selection_options(question)
        if only_one is None or not options:
            if question.routing:
                _unsupported(question.id, "routed selection needs valid options and only_one_option")
            # For non-routed questions, collect an unrestricted string rather
            # than guessing whether an ambiguous selection is single/multiple.
            # The full original settings survive in presentation metadata.
        elif _boolean_choices(question, required=required):
            schema = {"kind": "boolean"}
        else:
            schema = {"kind": "select_one" if only_one else "select_many", "options": options}
            if not required and only_one:
                if any(opt["value"] == "__forms_skip__" for opt in options):
                    _unsupported(question.id, "reserved optional selection value")
                schema["options"] = [*options, {"value": "__forms_skip__", "label": "Skip this question"}]
    # Other answer types, including unfamiliar *scalar* types, are string
    # inputs. Known structural types (file and selection) are handled above.
    if not required:
        schema["allow_skip"] = True
        if schema["kind"] == "string":
            schema["default"] = ""
    schema["presentation"] = _presentation(question)
    return schema


def compile_form(export: dict[str, Any]) -> dict[str, Any]:
    """Return a definition validated by the *actual* SFSMDefinition model."""
    content, questions = normalise_form(export)
    ids = {question.id for question in questions}
    states: dict[str, dict[str, Any]] = {}
    already_asked: set[str] = set()
    for question in questions:
        after = f"{question.id}__route" if question.routing else (question.next_id or "end_form")
        states[question.id] = {
            "type": "input",
            "prompt": question.data["question_text"],
            "schema": _schema(question),
            "assign": f"answers.{question.id}",
            "next": after,
        }
        if question.routing:
            rules = []
            for condition in question.routing:
                if not isinstance(condition, dict):
                    _unsupported(question.id, "routing condition must be an object")
                if condition.get("routing_page_id") not in (None, question.id):
                    _unsupported(question.id, "routing_page_id differs from the current page")
                check_id = condition.get("check_page_id") or question.id
                if check_id != question.id and check_id not in already_asked:
                    _unsupported(question.id, "cross-page condition must check a preceding question")
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
                check_id = condition.get("check_page_id") or question.id
                kind = states[check_id]["schema"]["kind"]
                path = f"answers.{check_id}"
                if kind == "boolean":
                    normalised = answer.strip().lower()
                    if normalised not in ("yes", "no", "true", "false"):
                        _unsupported(question.id, f"invalid boolean routing answer {answer!r}")
                    predicate = {"op": "is_true" if normalised in ("yes", "true") else "is_false", "path": path}
                elif kind in ("select_one", "select_many"):
                    values = {o["value"] for o in states[check_id]["schema"]["options"]}
                    if answer not in values:
                        _unsupported(question.id, f"routing answer_value {answer!r} missing from selection")
                    predicate = {"op": "contains" if kind == "select_many" else "eq",
                                 "path": path, "value": answer}
                elif kind == "string":
                    # Equality of the collected value is independent of the UI
                    # control that produced it. No agent decides progression.
                    predicate = {"op": "eq", "path": path, "value": answer}
                else:
                    _unsupported(question.id, f"cannot route on {kind} input")
                rules.append({"when": predicate, "next": target})
            states[f"{question.id}__route"] = {"type": "choice", "rules": rules,
                                               "default": question.next_id or "end_form"}
        already_asked.add(question.id)
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
