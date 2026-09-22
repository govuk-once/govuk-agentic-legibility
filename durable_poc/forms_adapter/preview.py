"""Local-only, no-agent SFSM preview; no Temporal or form submission.

The browser sees just the current input state. This runner uses the actual
SFSM model/predicates and follows only compiled SFSM transitions; it does not
implement a second Forms routing engine or send data to any department.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.model import ChoiceState, EndState, InputState, SFSMDefinition
from src.paths import set_path
from src.predicates import evaluate

DEFAULT_DIRECTORY = Path(__file__).resolve().parents[2] / "compiled_forms"


@dataclass
class PreviewRun:
    definition: SFSMDefinition
    state_id: str
    answers: dict[str, Any] = field(default_factory=dict)
    terminal: bool = False

    def current(self) -> dict[str, Any]:
        process = self.definition.processes[self.definition.entry]
        seen: set[str] = set()
        while True:
            if self.state_id in seen:
                raise ValueError(f"cycle with no input at {self.state_id}")
            seen.add(self.state_id)
            state = process.states[self.state_id]
            if isinstance(state, ChoiceState):
                context = {"answers": self.answers}
                self.state_id = next((rule.next for rule in state.rules if evaluate(rule.when, context)), state.default)
            elif isinstance(state, EndState):
                self.terminal = True
                return {"status": state.status, "terminal": True, "interaction": None,
                        "answers": self.answers}
            elif isinstance(state, InputState):
                schema = state.schema_
                presentation = schema.model_extra.get("presentation", {}) if schema.model_extra else {}
                kind = schema.kind
                prop: dict[str, Any] = {
                    "title": presentation.get("field_label") or presentation.get("question_text") or state.prompt,
                    "description": presentation.get("hint_text") or "",
                }
                if kind == "select_one":
                    prop.update(type="string", enum=[opt.value if hasattr(opt, "value") else opt for opt in schema.options or []])
                    prop["enum_labels"] = {opt.value: opt.label for opt in schema.options or [] if hasattr(opt, "value")}
                elif kind == "select_many":
                    prop.update(type="array", items={"type": "string", "enum": [opt.value if hasattr(opt, "value") else opt for opt in schema.options or []]})
                    prop["enum_labels"] = {opt.value: opt.label for opt in schema.options or [] if hasattr(opt, "value")}
                elif kind == "string":
                    prop["type"] = "string"
                    answer_type = presentation.get("answer_type")
                    if answer_type == "email":
                        prop["format"] = "email"
                    if answer_type == "date":
                        prop["format"] = "date"
                    if (presentation.get("answer_settings") or {}).get("input_type") == "long_text":
                        prop["ui_hint"] = "textarea"
                else:
                    raise ValueError(f"unsupported preview schema kind {kind}")
                required = not schema.allow_skip
                # Individual compound components can be optional even on a required question.
                # The metadata's per-field override is written by the compiler.
                if "required" in presentation:
                    required = bool(presentation["required"])
                return {"status": "in_progress", "terminal": False,
                        "interaction": {"id": self.state_id,
                                        "content": {"title": presentation.get("page_heading") or self.definition.defaults.get("forms", {}).get("name"),
                                                    "description": state.prompt,
                                                    "forms": presentation},
                                        "input_schema": {"type": "object", "properties": {"answer": prop},
                                                         "required": ["answer"] if required else []}},
                        "answers": self.answers}
            else:
                raise ValueError(f"unexpected preview state {type(state).__name__}")

    def submit(self, value: Any) -> dict[str, Any]:
        if self.terminal:
            raise ValueError("run already completed")
        state = self.definition.processes[self.definition.entry].states[self.state_id]
        if not isinstance(state, InputState):
            raise ValueError("run is not awaiting input")
        schema = state.schema_
        presentation = (schema.model_extra or {}).get("presentation", {})
        required = bool(presentation.get("required", not schema.allow_skip))
        if schema.kind == "string":
            if value is None and not required:
                value = ""
            if not isinstance(value, str) or (required and not value.strip()):
                raise ValueError("Enter a value")
        elif schema.kind in ("select_one", "select_many"):
            options = {opt.value for opt in schema.options or [] if hasattr(opt, "value")}
            if schema.kind == "select_one":
                if not required and value in (None, ""):
                    value = "__forms_skip__"
                if value not in options:
                    raise ValueError("Select an available option")
            elif not isinstance(value, list) or any(v not in options for v in value) or (required and not value):
                raise ValueError("Select one or more available options")
        else:
            raise ValueError(f"unsupported preview schema kind {schema.kind}")
        set_path({"answers": self.answers}, state.assign, value)
        self.state_id = state.next
        return self.current()


class SubmitRequest(BaseModel):
    answer: Any = None


def create_app(definitions_dir: Path | None = None) -> FastAPI:
    """Use a local directory of precompiled, model-validated SFSM files."""
    directory = definitions_dir or Path(os.environ.get("FORMS_COMPILED_DIR", DEFAULT_DIRECTORY))
    app = FastAPI(title="SFSM Forms local preview")
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    runs: dict[str, PreviewRun] = {}

    def load(form_id: str) -> SFSMDefinition:
        # Numerical IDs only: never allow this dev-only API to read arbitrary paths.
        if not form_id.isdecimal():
            raise HTTPException(400, "Form ID must be numeric")
        path = directory / f"{form_id}.json"
        if not path.is_file():
            raise HTTPException(404, "Compile the form before previewing it")
        try:
            definition = SFSMDefinition.model_validate_json(path.read_text(encoding="utf-8"))
            if definition.id != f"govuk.forms.{form_id}":
                raise ValueError("definition ID does not match filename")
            return definition
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, f"Invalid compiled definition: {exc}") from exc

    @app.get("/api/forms")
    def list_forms() -> list[dict[str, Any]]:
        forms = []
        for path in sorted(directory.glob("[0-9]*.json")) if directory.is_dir() else []:
            if path.stem.isdecimal():
                definition = load(path.stem)
                forms.append({"id": path.stem, "name": definition.defaults.get("forms", {}).get("name") or path.stem})
        return forms

    @app.post("/api/forms/{form_id}/runs")
    def start(form_id: str) -> dict[str, Any]:
        definition = load(form_id)
        run_id = uuid4().hex
        run = PreviewRun(definition=definition,
                         state_id=definition.processes[definition.entry].start)
        runs[run_id] = run
        return {"run_id": run_id, "form_id": form_id, **run.current()}

    @app.post("/api/forms/runs/{run_id}/answers")
    def submit(run_id: str, request: SubmitRequest) -> dict[str, Any]:
        run = runs.get(run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        try:
            return {"run_id": run_id, "form_id": run.definition.id.rsplit(".", 1)[-1], **run.submit(request.answer)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return app


app = create_app()
