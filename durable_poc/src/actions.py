"""State transformation and assignment handlers for FSM execution."""
from datetime import datetime, timedelta
import re
from typing import Any

from src.model import OperationSpec, OperationsRegistry
from src.paths import resolve_path

# Matches ISO 8601 Durations requiring at least one populated unit
DURATION_RE = re.compile(
    r"^P(?=.)(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)

# ---------------------------------------------------------------------------
# Schema templates — reusable JSON Schema shapes for operation specs
# ---------------------------------------------------------------------------

SCHEMA_TEMPLATES: dict[str, dict[str, Any]] = {
    "binary_numeric": {
        "type": "object",
        "properties": {
            "op": {"type": "string"},
            "path": {"type": "string", "description": "Dot-path to the first operand"},
            "value": {"type": "number", "description": "Literal second operand"},
            "value_path": {"type": "string", "description": "Dot-path to the second operand"},
        },
        "required": ["op", "path"],
        "oneOf": [{"required": ["value"]}, {"required": ["value_path"]}],
    },
    "binary_date": {
        "type": "object",
        "properties": {
            "op": {"type": "string"},
            "path": {"type": "string", "description": "Dot-path to the base date"},
            "value": {"type": "string", "description": "Offset string (e.g. '14 days', '2 months')"},
        },
        "required": ["op", "path", "value"],
    },
    "unary_duration": {
        "type": "object",
        "properties": {
            "op": {"type": "string"},
            "value_path": {"type": "string", "description": "Dot-path to an ISO 8601 duration string"},
        },
        "required": ["op", "value_path"],
    },
    "list_append": {
        "type": "object",
        "properties": {
            "op": {"type": "string"},
            "path": {"type": "string", "description": "Dot-path to the target list"},
            "value": {"description": "Literal value to append"},
            "value_path": {"type": "string", "description": "Dot-path to the value to append"},
        },
        "required": ["op", "path"],
        "oneOf": [{"required": ["value"]}, {"required": ["value_path"]}],
    },
}

# ---------------------------------------------------------------------------
# Registry and decorator
# ---------------------------------------------------------------------------

REGISTRY = OperationsRegistry()


def operation(
    description: str,
    schema: str | dict[str, Any],
    example: dict[str, Any] | None = None,
):
    def decorator(fn):
        resolved = SCHEMA_TEMPLATES[schema] if isinstance(schema, str) else schema
        REGISTRY.register(OperationSpec(
            name=fn.__name__,
            fn=fn,
            description=description,
            spec_schema=resolved,
            example=example,
        ))
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


@operation(
    description="Arithmetic addition of two numbers.",
    schema="binary_numeric",
    example={"op": "add", "path": "retry_count", "value": 1},
)
def add(spec: dict, context: dict) -> int | float | None:
    val1 = resolve_path(context, spec.get("path", ""))
    val2 = (
        resolve_path(context, spec["value_path"])
        if "value_path" in spec
        else spec.get("value")
    )
    if val1 is None or val2 is None:
        return None
    return val1 + val2


@operation(
    description="Arithmetic subtraction of two numbers.",
    schema="binary_numeric",
    example={"op": "subtract", "path": "balance", "value": 50},
)
def subtract(spec: dict, context: dict) -> int | float | None:
    val1 = resolve_path(context, spec.get("path", ""))
    val2 = (
        resolve_path(context, spec["value_path"])
        if "value_path" in spec
        else spec.get("value")
    )
    if val1 is None or val2 is None:
        return None
    return val1 - val2


@operation(
    description="Arithmetic multiplication of two numbers.",
    schema="binary_numeric",
    example={"op": "multiply", "path": "quantity", "value": 2},
)
def multiply(spec: dict, context: dict) -> int | float | None:
    val1 = resolve_path(context, spec.get("path", ""))
    val2 = (
        resolve_path(context, spec["value_path"])
        if "value_path" in spec
        else spec.get("value")
    )
    if val1 is None or val2 is None:
        return None
    return val1 * val2


@operation(
    description="Current time plus an ISO 8601 duration.",
    schema="unary_duration",
    example={"op": "now_plus", "value_path": "reminder_offset"},
)
def now_plus(spec: dict, context: dict) -> str | None:
    now = context.get("__now__")
    if now is None:
        return None
    dur_path = spec.get("value_path")
    if dur_path:
        dur_str = resolve_path(context, dur_path)
        if dur_str:
            dt = now + parse_duration(dur_str)
            return dt.isoformat()


@operation(
    description="Add an offset to a date.",
    schema="binary_date",
    example={"op": "date_add", "path": "start_date", "value": "14 days"},
)
def date_add(spec: dict, context: dict) -> str | None:
    base_date = resolve_path(context, spec.get("path", ""))
    offset_str = spec.get("value")
    return apply_date_math(base_date, offset_str, op_type="add")


@operation(
    description="Subtract an offset from a date.",
    schema="binary_date",
    example={"op": "date_subtract", "path": "due_date", "value": "7 days"},
)
def date_subtract(spec: dict, context: dict) -> str | None:
    base_date = resolve_path(context, spec.get("path", ""))
    offset_str = spec.get("value")
    return apply_date_math(base_date, offset_str, op_type="subtract")


@operation(
    description="Append a value to a list.",
    schema="list_append",
    example={"op": "append", "path": "selected_items", "value": "photo_update"},
)
def append(spec: dict, context: dict) -> list:
    current = resolve_path(context, spec.get("path", ""))
    current = list(current) if isinstance(current, list) else []
    value = (
        resolve_path(context, spec["value_path"])
        if "value_path" in spec
        else spec.get("value")
    )
    current.append(value)
    return current


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
        except (ValueError, TypeError):
            pass
    return None


def parse_duration(duration_str: str) -> timedelta:
    """Parse an ISO 8601 duration string into a timedelta."""
    if not duration_str or duration_str == "P":
        raise ValueError(f"Invalid duration format: '{duration_str}'")

    match = DURATION_RE.match(duration_str)
    if not match:
        raise ValueError(f"Invalid duration format: '{duration_str}'")

    groups = match.groupdict(default="0")
    days = int(groups["days"])
    hours = int(groups["hours"])
    minutes = int(groups["minutes"])
    seconds = float(groups["seconds"])

    if days == 0 and hours == 0 and minutes == 0 and seconds == 0:
        raise ValueError(f"Duration string '{duration_str}' resolved to 0 time")

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
