"""Unit tests for pure domain functions without Temporal overhead."""

from datetime import timedelta
import pytest

from src.paths import interpolate, parse_duration, resolve_dict, resolve_path
from src.predicates import evaluate


@pytest.mark.it("resolves paths")
def test_resolve_path() -> None:
    ctx = {"user": {"details": {"age": 30}}, "items": [10, 20]}
    assert resolve_path(ctx, "user.details.age") == 30
    assert resolve_path(ctx, "items.1") == 20
    assert resolve_path(ctx, "missing.path") is None


@pytest.mark.it("parses duration markers")
def test_parse_duration() -> None:
    assert parse_duration("PT30S") == timedelta(seconds=30)
    assert parse_duration("PT5M") == timedelta(minutes=5)
    assert parse_duration("P14D") == timedelta(days=14)

    with pytest.raises(ValueError):
        parse_duration("invalid")


def test_predicates() -> None:
    ctx = {"attempts": 2, "max_attempts": 3, "confirmed": True}

    assert evaluate({"op": "eq", "path": "attempts", "value": 2}, ctx) is True
    assert (
        evaluate({"op": "lt", "path": "attempts", "value_path": "max_attempts"}, ctx)
        is True
    )
    assert evaluate({"op": "is_true", "path": "confirmed"}, ctx) is True


@pytest.mark.it("resolves dictionaries")
def test_resolve_dict() -> None:
    ctx = {"postcode": "SW1A 1AA"}
    body = {"query": {"$": "postcode"}}
    assert resolve_dict(body, ctx) == {"query": "SW1A 1AA"}


@pytest.mark.it("interpolates strings inputs")
def test_interpolate() -> None:
    ctx = {"workflow_id": "123", "step": 5}
    assert interpolate("key:{{workflow_id}}:{{step}}", ctx) == "key:123:5"
