"""State transformation and assignment handlers for FSM execution."""

from datetime import datetime, timedelta
import re
from typing import Any


def apply_date_math(
    date_val: Any, offset_str: str | None, op_type: str = "subtract"
) -> str | None:
    """Adds or subtracts weeks, days, months, or years to/from a date string."""
    if not date_val or not offset_str:
        return None

    val_str = str(date_val).strip()
    dt = _parse_date(val_str)
    if not dt:
        return None

    match = re.search(r"(\d+)\s*(week|day|month|year)", str(offset_str).lower())
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    mult = 1 if op_type == "add" else -1

    if unit == "week":
        res_dt = dt + timedelta(weeks=amount * mult)
    elif unit == "day":
        res_dt = dt + timedelta(days=amount * mult)
    elif unit == "month":
        month = dt.month - 1 + (amount * mult)
        year = dt.year + month // 12
        month = month % 12 + 1
        day = min(
            dt.day,
            [
                31,
                29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                31,
                30,
                31,
                30,
                31,
                31,
                30,
                31,
                30,
                31,
            ][month - 1],
        )
        res_dt = dt.replace(year=year, month=month, day=day)
    elif unit == "year":
        res_dt = dt.replace(year=dt.year + (amount * mult))
    else:
        return None

    if "/" in val_str:
        return res_dt.strftime("%d/%m/%Y")
    return res_dt.strftime("%Y-%m-%d")


def _parse_date(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    val_str = str(val).strip().split(".")[0]

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError, TypeError:
            pass
    return None
