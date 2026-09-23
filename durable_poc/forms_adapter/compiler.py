"""GOV.UK Forms -> SFSM/0.2 journey compiler.

SFSM is deliberately the output contract: progression is represented by ``next``
references and native ``choice`` predicates, never by a client or an agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    exit_pages: list[dict[str, Any]] = field(default_factory=list)


def _unsupported(where: str, reason: str) -> None:
    raise UnsupportedForm(f"{where}: {reason}")


def normalise_form(export: dict[str, Any]) -> tuple[dict[str, Any], list[Question]]:
    """Both ``question_page`` and ``question`` have the same core semantics."""
    content = export.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("steps"), list):
        _unsupported("form", "expected content.steps array")
    if not str(content.get("form_id") or export.get("form_id") or "").isdigit():
        _unsupported("form", "missing or non-numeric form_id")
    # payment_url is preserved in form metadata but payment is not functional.
    steps: list[Question] = []
    seen: set[str] = set()
    for item in content["steps"]:
        where = f"step {item.get('id', '<missing>')}"
        if item.get("type") not in ("question", "question_page"):
            _unsupported(where, f"unsupported step type {item.get('type')!r}")
        # exit_pages are resolved during routing compilation.
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
        # One input state cannot implement the Forms "add another" loop.
        if data["is_repeatable"]:
            _unsupported(where, "repeatable question is not implemented")
        sid = item.get("id")
        if not isinstance(sid, str) or not sid or sid in seen or "__" in sid:
            _unsupported(where, "missing, duplicate or reserved step ID")
        seen.add(sid)
        if not isinstance(data.get("question_text"), str) or not data["question_text"].strip():
            _unsupported(where, "missing question_text")
        routing = item.get("routing_conditions") or []
        if not isinstance(routing, list):
            _unsupported(where, "routing_conditions must be an array")
        exit_pages = item.get("exit_pages")
        if exit_pages is None:
            exit_pages = []
        if not isinstance(exit_pages, list):
            _unsupported(where, "exit_pages must be an array")
        steps.append(Question(sid, data, item.get("next_step_id"), routing, item.get("position", 0), exit_pages))
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
        "is_repeatable": data.get("is_repeatable", False),
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
        settings = question.data.get("answer_settings") or {}
        if not isinstance(settings, dict):
            _unsupported(question.id, "invalid file answer_settings")
        for key in ("max_files", "maximum_number_of_files", "max_number_of_files"):
            count = settings.get(key)
            if count is not None and (isinstance(count, bool) or str(count) != "1"):
                _unsupported(question.id, "multiple file uploads are not supported")
        if settings.get("allow_multiple_files") in (True, "true"):
            _unsupported(question.id, "multiple file uploads are not supported")
        # A supplied optional file is still a file_ref, not a string.
        schema = {"kind": "file_ref"}
    elif answer_type == "selection":
        only_one, options = _selection_options(question)
        if only_one is None or not options:
            _unsupported(question.id, "selection needs valid options and only_one_option")
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
    """Compile only routes and inputs whose semantics can be preserved."""
    content, questions = normalise_form(export)
    ids = {question.id for question in questions}
    states: dict[str, dict[str, Any]] = {}
    already_asked: set[str] = set()
    for question in questions:
        where = f"step {question.id}"
        exit_pages: dict[Any, dict[str, Any]] = {}
        for page in question.exit_pages:
            if not isinstance(page, dict) or page.get("id") is None:
                _unsupported(where, "invalid exit_pages entry (missing id)")
            page_id = page["id"]
            if not isinstance(page_id, (str, int)) or isinstance(page_id, bool):
                _unsupported(where, "invalid exit_page id")
            if page_id in exit_pages:
                _unsupported(where, f"duplicate exit_page id {page_id!r}")
            exit_pages[page_id] = page
        used_exits: set[Any] = set()
        after = f"{question.id}__route" if question.routing else (question.next_id or "end_form")
        states[question.id] = {
            "type": "input", "prompt": question.data["question_text"],
            "schema": _schema(question), "assign": f"answers.{question.id}",
            "next": after,
        }
        if question.routing:
            rules = []
            unconditional: str | None = None
            exit_counter = 0
            for condition in question.routing:
                if not isinstance(condition, dict):
                    _unsupported(where, "routing condition must be an object")
                if condition.get("routing_page_id") not in (None, question.id):
                    _unsupported(where, "routing_page_id differs from the current page")
                check_id = condition.get("check_page_id") or question.id
                if check_id != question.id and check_id not in already_asked:
                    _unsupported(where, "cross-page condition must check a preceding question")
                if condition.get("validation_errors"):
                    _unsupported(where, "routing condition contains validation errors")
                skip = condition.get("skip_to_end")
                if skip is not None and not isinstance(skip, bool):
                    _unsupported(where, "skip_to_end must be a boolean")
                goto = condition.get("goto_page_id")
                ep_id = condition.get("exit_page_id")
                inline_heading = condition.get("exit_page_heading")
                inline_markdown = condition.get("exit_page_markdown")
                has_inline = inline_heading is not None or inline_markdown is not None
                if skip and (goto is not None or ep_id is not None or has_inline):
                    _unsupported(where, "ambiguous skip_to_end and another destination")
                if goto is not None and (ep_id is not None or has_inline):
                    _unsupported(where, "ambiguous goto_page_id and exit page")
                if ep_id is not None and has_inline:
                    _unsupported(where, "ambiguous exit_page_id and inline content")
                if ep_id is not None:
                    if ep_id not in exit_pages:
                        _unsupported(where, f"unknown exit_page_id {ep_id!r}")
                    used_exits.add(ep_id)
                    heading = exit_pages[ep_id].get("heading")
                    markdown = exit_pages[ep_id].get("markdown")
                else:
                    heading, markdown = inline_heading, inline_markdown
                if ep_id is not None or has_inline:
                    if ((heading is not None and not isinstance(heading, str))
                            or (markdown is not None and not isinstance(markdown, str))):
                        _unsupported(where, "exit page heading and markdown must be strings")
                    message = "\n\n".join(part.strip() for part in (heading, markdown)
                                          if isinstance(part, str) and part.strip())
                    if not message:
                        _unsupported(where, "exit page is missing content")
                    exit_counter += 1
                    target = f"{question.id}__exit_{exit_counter}"
                    end_id = f"{target}__end"
                    states[target] = {"type": "output", "channel": "transcript",
                                      "message": message, "next": end_id}
                    states[end_id] = {"type": "end", "status": "offramp", "outcome": "exit_page"}
                elif skip:
                    target = "end_form"
                elif goto is not None:
                    if goto not in ids:
                        _unsupported(where, f"invalid routing target {goto!r}")
                    target = goto
                else:
                    _unsupported(where, "routing condition has no destination")
                answer = condition.get("answer_value")
                if answer is None:
                    if unconditional is not None:
                        _unsupported(where, "multiple unconditional routing conditions")
                    unconditional = target
                    continue
                if not isinstance(answer, str):
                    _unsupported(where, "routing requires a string answer_value")
                kind = states[check_id]["schema"]["kind"]
                path = f"answers.{check_id}"
                if kind == "boolean":
                    normalised = answer.strip().lower()
                    if normalised not in ("yes", "no", "true", "false"):
                        _unsupported(where, f"invalid boolean routing answer {answer!r}")
                    predicate = {"op": "is_true" if normalised in ("yes", "true") else "is_false", "path": path}
                elif kind in ("select_one", "select_many"):
                    values = {o["value"] for o in states[check_id]["schema"]["options"]}
                    if answer not in values:
                        _unsupported(where, f"routing answer_value {answer!r} missing from selection")
                    predicate = {"op": "contains" if kind == "select_many" else "eq",
                                 "path": path, "value": answer}
                elif kind == "string":
                    predicate = {"op": "eq", "path": path, "value": answer}
                else:
                    _unsupported(where, f"cannot route on {kind} input")
                rules.append({"when": predicate, "next": target})
            if set(exit_pages) != used_exits:
                _unsupported(where, "unreferenced exit_pages; routing semantics are unknown")
            if rules:
                states[f"{question.id}__route"] = {
                    "type": "choice", "rules": rules,
                    "default": unconditional or question.next_id or "end_form"}
            else:
                states[question.id]["next"] = unconditional or question.next_id or "end_form"
        elif exit_pages:
            _unsupported(where, "exit_pages are present without routing_conditions")
        already_asked.add(question.id)
    if "end_form" in states or any(q.id == "end_form" for q in questions):
        _unsupported("form", "reserved end_form state ID")
    states["end_form"] = {"type": "end", "status": "success", "outcome": "form_answers_collected"}
    for sid, state in states.items():
        for target in ([state["next"]] if state["type"] in ("input", "output") else
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
                              "payment_url": content.get("payment_url"),
                              "preview_only": True}},
        "processes": {"main": {"start": content.get("start_page") or questions[0].id,
                                "vars": {"answers": {}}, "states": states}},
    }
    SFSMDefinition.model_validate(definition)
    return definition
