"""Pure predicate evaluation without execution engines."""

from datetime import datetime
import re
from typing import Any

from src.paths import resolve_path


def evaluate(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a JSON-serialised predicate against the runtime context."""
    op = condition.get("op")
    if not op:
        raise ValueError("Condition missing 'op' key.")

    # Equals / Strict / Case-Insensitive String Equality
    if op in ["eq", "equals"]:
        path_val = resolve_path(context, condition["path"])
        cmp_val = _resolve_value(condition, context)
        if path_val is None or cmp_val is None:
            return path_val == cmp_val
        if type(path_val) is type(cmp_val):
            return path_val == cmp_val
        return str(path_val).strip().lower() == str(cmp_val).strip().lower()

    # Numeric Comparisons (Less Than / Less Than or Equal)
    elif op in ["lt", "lte", "less_than", "less_than_or_equal"]:
        path_val = resolve_path(context, condition["path"])
        cmp_val = _resolve_value(condition, context)
        if path_val is None or cmp_val is None:
            return False
        try:
            p_num, c_num = float(path_val), float(cmp_val)
            return p_num < c_num if op in ["lt", "less_than"] else p_num <= c_num
        except ValueError, TypeError:
            return False

    # Numeric Comparisons (Greater Than / Greater Than or Equal)
    elif op in ["gt", "gte", "greater_than", "greater_than_or_equal"]:
        path_val = resolve_path(context, condition["path"])
        cmp_val = _resolve_value(condition, context)
        if path_val is None or cmp_val is None:
            return False
        try:
            p_num, c_num = float(path_val), float(cmp_val)
            return p_num > c_num if op in ["gt", "greater_than"] else p_num >= c_num
        except ValueError, TypeError:
            return False

    # Boolean Checks
    elif op == "is_true":
        val = resolve_path(context, condition["path"])
        if isinstance(val, bool):
            return val is True
        if isinstance(val, str):
            return val.strip().lower() in ["true", "y", "yes", "1"]
        return bool(val)

    elif op == "is_false":
        val = resolve_path(context, condition["path"])
        if isinstance(val, bool):
            return val is False
        if isinstance(val, str):
            return val.strip().lower() in ["false", "n", "no", "0"]
        return False

    # Emptiness Checks
    elif op == "not_empty":
        val = resolve_path(context, condition["path"])
        return bool(val) and val != ""

    # Logical Combinators
    elif op == "and":
        subs = condition.get("all") or condition.get("rules") or []
        return all(evaluate(sub, context) for sub in subs)

    elif op == "or":
        subs = condition.get("any") or condition.get("rules") or []
        return any(evaluate(sub, context) for sub in subs)

    elif op == "not":
        sub = condition.get("condition") or condition.get("rule")
        if not sub:
            raise ValueError("Operator 'not' requires a 'condition' or 'rule' key.")
        return not evaluate(sub, context)

    # Date Evaluation Operations (Strictly Deterministic via context['__now__'])
    elif op == "date_before":
        val1 = resolve_path(context, condition.get("path", "")) or resolve_path(
            context, "__now__"
        )
        val2 = _resolve_value(condition, context)

        d1 = _parse_date(val1)
        d2 = _parse_date(val2)

        if d1 is None or d2 is None:
            return False
        return bool(d1 < d2)

    elif op == "before_now":
        now_ts = resolve_path(context, "__now__")
        if not now_ts:
            raise KeyError("Runtime context missing deterministic '__now__' key")

        target_ts = resolve_path(context, condition["path"])
        if target_ts is None:
            return False

        now_dt = _parse_date(now_ts)
        target_dt = _parse_date(target_ts)

        if now_dt is None or target_dt is None:
            return False
        return bool(target_dt < now_dt)

    elif op == "date_diff_greater_than":
        target_ts = resolve_path(context, condition["path"])
        now_ts = resolve_path(context, "__now__")
        if target_ts is None or now_ts is None:
            return False

        target_dt = _parse_date(target_ts)
        now_dt = _parse_date(now_ts)

        if target_dt is None or now_dt is None:
            return False

        diff_days = abs((now_dt - target_dt).days)
        val_str = str(condition.get("value", "")).lower()

        match = re.search(r"\d+", val_str)
        num = int(match.group()) if match else 1

        if "month" in val_str:
            return diff_days > (num * 30)
        elif "week" in val_str:
            return diff_days > (num * 7)
        elif "day" in val_str:
            return diff_days > num
        return False

    # Substring & Array Membership Checks
    elif op in ["contains", "in", "includes"]:
        path_val = resolve_path(context, condition["path"])
        cmp_val = _resolve_value(condition, context)
        if path_val is None or cmp_val is None:
            return False

        # Exact item matching for Python lists (e.g. select_many inputs)
        if isinstance(path_val, list):
            cmp_str = str(cmp_val).strip().lower()
            return any(str(item).strip().lower() == cmp_str for item in path_val)

        # Standard substring checking for raw strings
        return str(cmp_val).strip().lower() in str(path_val).strip().lower()

    raise ValueError(f"Unrecognised operator: {op}")


def _resolve_value(condition: dict[str, Any], context: dict[str, Any]) -> Any:
    """Extract direct literals or resolve dynamic path values."""
    if "value" in condition:
        return condition["value"]
    if "value_path" in condition:
        return resolve_path(context, condition["value_path"])
    return None


def _parse_date(val: Any) -> datetime | None:
    """Attempt parsing ISO or UK DD/MM/YYYY date strings into datetime objects."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    val_str = str(val).strip()

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(val_str.split(".")[0], fmt)
        except ValueError, TypeError:
            pass

    return None
