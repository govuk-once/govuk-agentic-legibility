"""Pure predicate evaluation without execution engines."""

from datetime import datetime
import re
from typing import Any

from src.model import Condition
from src.paths import resolve_path


def evaluate(condition: Condition, context: dict[str, Any]) -> bool:
    """Evaluate a Condition against runtime context."""
    op = condition.op
    if not op:
        raise ValueError("Condition missing 'op' key.")

    # Equals / Strict / Case-Insensitive String Equality
    if op == "eq":
        path_val = resolve_path(context, condition.path or "")
        cmp_val = _resolve_value(condition, context)
        if path_val is None or cmp_val is None:
            return path_val == cmp_val
        if type(path_val) is type(cmp_val):
            return path_val == cmp_val
        return str(path_val).strip().lower() == str(cmp_val).strip().lower()

    # Numeric Comparisons (Less Than / Less Than or Equal)
    elif op in ("lt", "lte"):
        path_val = resolve_path(context, condition.path or "")
        cmp_val = _resolve_value(condition, context)
        if path_val is None or cmp_val is None:
            return False
        try:
            p_num, c_num = float(path_val), float(cmp_val)
            return p_num < c_num if op in ["lt"] else p_num <= c_num
        except (ValueError, TypeError):
            return False

    # Numeric Comparisons (Greater Than / Greater Than or Equal)
    elif op in ("gt", "gte"):
        path_val = resolve_path(context, condition.path or "")
        cmp_val = _resolve_value(condition, context)
        if path_val is None or cmp_val is None:
            return False
        try:
            p_num, c_num = float(path_val), float(cmp_val)
            return p_num > c_num if op in ["gt"] else p_num >= c_num
        except (ValueError, TypeError):
            return False

    # Boolean Checks
    elif op == "is_true":
        val = resolve_path(context,condition.path or "")
        if isinstance(val, bool):
            return val is True
        if isinstance(val, str):
            return val.strip().lower() in ["true", "y", "yes", "1"]
        return bool(val)

    elif op == "is_false":
        val = resolve_path(context, condition.path or "")
        if isinstance(val, bool):
            return val is False
        if isinstance(val, str):
            return val.strip().lower() in ["false", "n", "no", "0"]
        return False

    # Emptiness Checks
    elif op == "not_empty":
        val = resolve_path(context, condition.path or "")
        if val is None:
            return False
        if val == "":
            return False
        if isinstance(val, (list, dict)):
            return len(val) > 0
        return True

    # Logical Combinators
    elif op == "and":
        return all(evaluate(child, context) for child in (condition.all or []))

    elif op == "or":
        return any(evaluate(child, context) for child in (condition.any or []))

    elif op == "not":
        conditions = condition.all or []
        if len(conditions) != 1:
            raise ValueError("Operator 'not' requires exactly one child 'condition'")
        return not evaluate(conditions[0], context)

    # Date Evaluation Operations (Strictly Deterministic via context['__now__'])
    elif op == "date_before":
        val1 = resolve_path(context, condition.path or "") or resolve_path(
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

        target_ts = resolve_path(context, condition.path or "")
        if target_ts is None:
            return False

        now_dt = _parse_date(now_ts)
        target_dt = _parse_date(target_ts)

        if now_dt is None or target_dt is None:
            return False
        return bool(target_dt < now_dt)

    elif op == "date_diff_greater_than":
        target_ts = resolve_path(context, condition.path or "")
        now_ts = resolve_path(context, "__now__")
        if target_ts is None or now_ts is None:
            return False

        target_dt = _parse_date(target_ts)
        now_dt = _parse_date(now_ts)

        if target_dt is None or now_dt is None:
            return False

        diff_days = abs((now_dt - target_dt).days)
        val_str = str(condition.value or "").lower()

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
    elif op == "contains":
        path_val = resolve_path(context, condition.path or "")
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


def _resolve_value(condition: Condition, context: dict[str, Any]) -> Any:
    """Extract direct literals or resolve dynamic path values."""
    if condition.value is not None:
        return condition.value

    if condition.value_path:
        return resolve_path(context, condition.value_path)
    return None


def _parse_date(val: Any) -> datetime | None:
    """Parse ISO or UK DD/MM/YYYY date strings into datetime objects."""
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
        except (ValueError, TypeError):
            pass

    return None
