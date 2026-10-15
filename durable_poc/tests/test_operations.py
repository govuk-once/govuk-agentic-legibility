"""Unit tests for operations and the registry."""

from datetime import datetime, timedelta

import pytest

from src.actions import (
    REGISTRY,
    add,
    append,
    date_add,
    date_subtract,
    multiply,
    now_plus,
    subtract,
)
from src.model import (
    InvalidSpecNameException,
    OperationSpec,
    OperationsRegistry,
)


# ---------------------------------------------------------------------------
# Arithmetic operations
# ---------------------------------------------------------------------------


class TestAdd:
    def test_literal_value(self):
        ctx = {"count": 5}
        assert add({"path": "count", "value": 3}, ctx) == 8

    def test_value_path(self):
        ctx = {"a": 10, "b": 7}
        assert add({"path": "a", "value_path": "b"}, ctx) == 17

    def test_missing_operand_returns_none(self):
        assert add({"path": "missing", "value": 1}, {"x": 1}) is None

    def test_float_operands(self):
        ctx = {"price": 9.99}
        assert add({"path": "price", "value": 0.01}, ctx) == pytest.approx(10.0)


class TestSubtract:
    def test_literal_value(self):
        ctx = {"balance": 100}
        assert subtract({"path": "balance", "value": 25}, ctx) == 75

    def test_value_path(self):
        ctx = {"total": 50, "discount": 10}
        assert subtract({"path": "total", "value_path": "discount"}, ctx) == 40

    def test_missing_operand_returns_none(self):
        assert subtract({"path": "missing", "value": 1}, {}) is None


class TestMultiply:
    def test_literal_value(self):
        ctx = {"qty": 4}
        assert multiply({"path": "qty", "value": 3}, ctx) == 12

    def test_value_path(self):
        ctx = {"rate": 15, "hours": 8}
        assert multiply({"path": "rate", "value_path": "hours"}, ctx) == 120

    def test_missing_operand_returns_none(self):
        assert multiply({"path": "missing", "value": 2}, {}) is None


# ---------------------------------------------------------------------------
# Date operations
# ---------------------------------------------------------------------------


class TestDateAdd:
    def test_add_days(self):
        ctx = {"start": "2026-01-01"}
        assert date_add({"path": "start", "value": "14 days"}, ctx) == "2026-01-15"

    def test_add_months(self):
        ctx = {"start": "2026-01-31"}
        assert date_add({"path": "start", "value": "1 month"}, ctx) == "2026-02-28"

    def test_missing_date_returns_none(self):
        assert date_add({"path": "missing", "value": "1 day"}, {}) is None


class TestDateSubtract:
    def test_subtract_days(self):
        ctx = {"due": "2026-03-15"}
        assert date_subtract({"path": "due", "value": "7 days"}, ctx) == "2026-03-08"

    def test_missing_offset_returns_none(self):
        ctx = {"due": "2026-03-15"}
        assert date_subtract({"path": "due"}, ctx) is None


class TestNowPlus:
    def test_adds_duration_from_iso_string(self):
        ctx = {"__now__": "2026-06-01T12:00:00", "offset": "PT30M"}
        result = now_plus({"value_path": "offset"}, ctx)
        assert result == "2026-06-01T12:30:00"

    def test_adds_duration_from_datetime(self):
        now = datetime(2026, 6, 1, 12, 0, 0)
        ctx = {"__now__": now, "offset": "PT30M"}
        result = now_plus({"value_path": "offset"}, ctx)
        assert result == (now + timedelta(minutes=30)).isoformat()

    def test_missing_now_returns_none(self):
        assert now_plus({"value_path": "offset"}, {"offset": "PT1H"}) is None

    def test_missing_duration_returns_none(self):
        ctx = {"__now__": datetime.now()}
        assert now_plus({"value_path": "missing"}, ctx) is None


# ---------------------------------------------------------------------------
# Collection operations
# ---------------------------------------------------------------------------


class TestAppend:
    def test_append_to_existing_list(self):
        ctx = {"items": ["a", "b"]}
        result = append({"path": "items", "value": "c"}, ctx)
        assert result == ["a", "b", "c"]

    def test_append_creates_list_when_missing(self):
        result = append({"path": "missing", "value": "first"}, {})
        assert result == ["first"]

    def test_append_with_value_path(self):
        ctx = {"items": [1], "next_val": 2}
        result = append({"path": "items", "value_path": "next_val"}, ctx)
        assert result == [1, 2]

    def test_does_not_mutate_original(self):
        original = ["x"]
        ctx = {"items": original}
        append({"path": "items", "value": "y"}, ctx)
        assert original == ["x"]

    def test_rejects_non_list_target(self):
        ctx = {"name": "Alice"}
        with pytest.raises(ValueError, match="must be a list"):
            append({"path": "name", "value": "Bob"}, ctx)

    def test_rejects_none_value(self):
        with pytest.raises(ValueError, match="resolved no value"):
            append({"path": "items", "value_path": "missing"}, {})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestOperationsRegistry:
    def test_global_registry_has_all_ops(self):
        names = {op.name for op in REGISTRY.list_ops()}
        assert names == {
            "add", "subtract", "multiply",
            "now_plus", "date_add", "date_subtract",
            "append",
            "eq", "lt", "gt", "is_true", "is_false",
            "date_before", "before_now",
        }

    def test_execute_returns_result(self):
        ctx = {"x": 10}
        result = REGISTRY.execute("add", {"path": "x", "value": 5}, ctx)
        assert result == 15

    def test_get_op_returns_spec(self):
        spec = REGISTRY.get_op("multiply")
        assert spec.name == "multiply"
        assert callable(spec.fn)

    def test_get_op_unknown_raises(self):
        with pytest.raises(InvalidSpecNameException):
            REGISTRY.get_op("nonexistent")

    def test_duplicate_registration_raises(self):
        registry = OperationsRegistry()
        spec = OperationSpec(
            name="dup",
            fn=lambda s, c: None,
            description="test",
            spec_schema={},
        )
        registry.register(spec)
        with pytest.raises(InvalidSpecNameException):
            registry.register(spec)
