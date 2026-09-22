"""Tests for the answer proposal logic."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_repo = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo / "durable_poc"))

from forms_frontend.api.proposals import (
    _coerce_proposal_value,
    _parse_proposal_response,
)


# =====================================================================
# Coercion
# =====================================================================


class TestCoerceProposalValue:
    def test_boolean_true(self):
        assert _coerce_proposal_value(True, {"kind": "boolean"}) is True

    def test_boolean_false(self):
        assert _coerce_proposal_value(False, {"kind": "boolean"}) is False

    def test_boolean_from_string_yes(self):
        assert _coerce_proposal_value("yes", {"kind": "boolean"}) is True

    def test_boolean_from_string_no(self):
        assert _coerce_proposal_value("no", {"kind": "boolean"}) is False

    def test_string_passthrough(self):
        assert _coerce_proposal_value("hello", {"kind": "string"}) == "hello"

    def test_string_coerces_int(self):
        assert _coerce_proposal_value(42, {"kind": "string"}) == "42"

    def test_select_one_exact_value(self):
        schema = {
            "kind": "select_one",
            "options": [
                {"value": "Very satisfied", "label": "Very satisfied"},
                {"value": "Satisfied", "label": "Satisfied"},
            ],
        }
        assert _coerce_proposal_value("Satisfied", schema) == "Satisfied"

    def test_select_one_case_insensitive(self):
        schema = {
            "kind": "select_one",
            "options": [
                {"value": "Very satisfied", "label": "Very satisfied"},
            ],
        }
        assert _coerce_proposal_value("very satisfied", schema) == "Very satisfied"

    def test_select_one_by_label(self):
        schema = {
            "kind": "select_one",
            "options": [
                {"value": "opt_a", "label": "Option A"},
            ],
        }
        assert _coerce_proposal_value("Option A", schema) == "opt_a"

    def test_select_many_list(self):
        result = _coerce_proposal_value(["a", "b"], {"kind": "select_many"})
        assert result == ["a", "b"]

    def test_select_many_csv_string(self):
        result = _coerce_proposal_value("a, b, c", {"kind": "select_many"})
        assert result == ["a", "b", "c"]


# =====================================================================
# Response parsing
# =====================================================================


class TestParseProposalResponse:
    def test_valid_json(self):
        response = '{"has_answer": true, "value": "test", "explanation": "from conversation"}'
        result = _parse_proposal_response(response, {"kind": "string"})
        assert result["has_answer"] is True
        assert result["value"] == "test"

    def test_json_in_markdown_fence(self):
        response = '```json\n{"has_answer": true, "value": false, "explanation": "user said no"}\n```'
        result = _parse_proposal_response(response, {"kind": "boolean"})
        assert result["has_answer"] is True
        assert result["value"] is False

    def test_json_with_surrounding_text(self):
        response = 'Here is my answer: {"has_answer": true, "value": "Satisfied", "explanation": "test"} Done.'
        result = _parse_proposal_response(response, {"kind": "string"})
        assert result["has_answer"] is True
        assert result["value"] == "Satisfied"

    def test_no_answer(self):
        response = '{"has_answer": false, "value": null, "explanation": "not enough info"}'
        result = _parse_proposal_response(response, {"kind": "string"})
        assert result["has_answer"] is False
        assert result["value"] is None

    def test_unparseable_response(self):
        response = "I cannot determine the answer from the conversation."
        result = _parse_proposal_response(response, {"kind": "string"})
        assert result["has_answer"] is False

    def test_boolean_coercion_in_parsed_response(self):
        response = '{"has_answer": true, "value": false, "explanation": "user said no"}'
        result = _parse_proposal_response(response, {"kind": "boolean"})
        assert result["value"] is False

    def test_select_one_coercion_in_parsed_response(self):
        schema = {
            "kind": "select_one",
            "options": [
                {"value": "Very satisfied", "label": "Very satisfied"},
                {"value": "Satisfied", "label": "Satisfied"},
            ],
        }
        response = '{"has_answer": true, "value": "satisfied", "explanation": "user said so"}'
        result = _parse_proposal_response(response, schema)
        assert result["value"] == "Satisfied"


# =====================================================================
# Presentation metadata preservation
# =====================================================================


def test_form_2130_has_presentation(form_2130_definition):
    """Verify that compiled form 2130 preserves presentation metadata."""
    states = form_2130_definition["processes"]["main"]["states"]

    first_state = states["Z9qiMdb6"]
    assert first_state["type"] == "input"
    pres = first_state["schema"]["presentation"]
    assert pres["answer_type"] == "selection"
    assert pres["question_text"] == "How are you using this service?"

    # Boolean question
    boolean_state = states["mq4KgkUb"]
    assert boolean_state["schema"]["kind"] == "boolean"
    assert boolean_state["schema"]["presentation"]["answer_type"] == "selection"

    # Email question (optional)
    email_state = states["31pMZdRv"]
    assert email_state["schema"]["presentation"]["answer_type"] == "email"
    assert email_state["schema"]["presentation"]["is_optional"] is True


def test_form_6_has_diverse_answer_types(form_6_definition):
    """Verify that compiled form 6 preserves diverse answer types."""
    states = form_6_definition["processes"]["main"]["states"]

    # Name input
    name_state = states["uyQrCFqM"]
    pres = name_state["schema"]["presentation"]
    assert pres["answer_type"] == "name"
    assert pres["answer_settings"]["input_type"] == "first_and_last_name"

    # NI number
    ni_state = states["opyfSJWo"]
    assert ni_state["schema"]["presentation"]["answer_type"] == "national_insurance_number"

    # Date of birth
    dob_state = states["8FTw3t4z"]
    pres = dob_state["schema"]["presentation"]
    assert pres["answer_type"] == "date"
    assert pres["answer_settings"]["input_type"] == "date_of_birth"

    # Address
    addr_state = states["v2rxCDt3"]
    assert addr_state["schema"]["presentation"]["answer_type"] == "address"


# =====================================================================
# Deterministic routing in form 2130
# =====================================================================


def test_form_2130_has_conditional_branches(form_2130_definition):
    """Verify the compiled SFSM has the expected choice states."""
    states = form_2130_definition["processes"]["main"]["states"]

    # First branch: boolean false → skip to email
    route1 = states["mq4KgkUb__route"]
    assert route1["type"] == "choice"
    assert route1["rules"][0]["when"]["op"] == "is_false"
    assert route1["rules"][0]["next"] == "31pMZdRv"
    assert route1["default"] == "bKCtg9gW"

    # Second branch: specific select_one value → skip
    route2 = states["dKg1ApnD__route"]
    assert route2["type"] == "choice"
    assert route2["rules"][0]["when"]["op"] == "eq"
    assert route2["rules"][0]["when"]["value"] == "A friend, relative or work colleague"
    assert route2["rules"][0]["next"] == "31pMZdRv"
