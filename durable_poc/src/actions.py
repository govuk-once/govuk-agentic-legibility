"""State transformation and assignment handlers for FSM execution."""

from datetime import datetime, timedelta
import re
from typing import Any

from src.paths import resolve_path


def execute_assign_state(state_def: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Process a 'type': 'assign' state and update runtime context."""
    set_operations = state_def.get("set", {})
    
    for var_name, expr in set_operations.items():
        if not isinstance(expr, dict):
            context[var_name] = expr
            continue

        op = expr.get("op")

        if op == "date_subtract":
            base_date = resolve_path(context, expr["path"])
            offset = expr.get("value")
            context[var_name] = apply_date_subtract(base_date, offset)

        elif op == "add":
            curr_val = resolve_path(context, expr["path"]) or 0
            add_val = expr.get("value", 0)
            context[var_name] = curr_val + add_val

        else:
            raise ValueError(f"Unrecognised assignment operator: {op}")

    return context


def apply_date_subtract(date_val: Any, offset_str: str) -> str | None:
    """Subtracts weeks, days, or months from a date string and returns an ISO/UK string."""
    dt = _parse_date(date_val)
    if not dt or not offset_str:
        return None

    offset_clean = str(offset_str).lower().strip()
    match = re.search(r"(\d+)\s*(week|day|month|year)", offset_clean)
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    if unit == "week":
        result_dt = dt - timedelta(weeks=amount)
    elif unit == "day":
        result_dt = dt - timedelta(days=amount)
    elif unit == "month":
        result_dt = dt - timedelta(days=amount * 30)  # Standard MA1 approximation
    elif unit == "year":
        result_dt = dt - timedelta(days=amount * 365)
    else:
        return None

    # Retain UK format (DD/MM/YYYY) if input used slashes, otherwise output ISO (YYYY-MM-DD)
    if "/" in str(date_val):
        return result_dt.strftime("%d/%m/%Y")
    return result_dt.strftime("%Y-%m-%d")


def _parse_date(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    val_str = str(val).strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(val_str.split(".")[0], fmt)
        except (ValueError, TypeError):
            pass
    return None