"""State transformation and assignment handlers for FSM execution."""
from datetime import datetime, timedelta
import re
from typing import Any

from src.model import Condition, OperationSpec, OperationsRegistry
from src.paths import resolve_path
from src.predicates import evaluate

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
    "predicate": {
        "type": "object",
        "properties": {
            "op": {"type": "string"},
            "path": {"type": "string", "description": "Dot-path to the value to test"},
            "value": {"description": "Literal comparison value"},
            "value_path": {"type": "string", "description": "Dot-path to the comparison value"},
            "all": {"type": "array", "description": "Child conditions for 'and' and 'not' operators"},
            "any": {"type": "array", "description": "Child conditions for 'or' operators"},
        },
        "required": ["op"],
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
    """Decorator that registers a function as a named operation in the global REGISTRY.

    The operation name is derived from the decorated function's ``__name__``.
    A schema template key (string) is resolved from ``SCHEMA_TEMPLATES``;
    alternatively a raw JSON Schema dict may be passed directly.

    Args:
        description: Human-readable one-line summary of the operation.
        schema: A key into ``SCHEMA_TEMPLATES`` or a raw JSON Schema dict
            describing the operation's spec shape.
        example: Optional example spec dict shown in discovery APIs.

    Returns:
        A decorator that registers the wrapped function and returns it
        unchanged.
    """
    def decorator(fn):
        """Register *fn* as an OperationSpec and return it unchanged."""
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
    """Sum two numeric values resolved from *spec* and *context*.

    Args:
        spec: Operation spec with ``path`` and either ``value`` or
            ``value_path``.
        context: Runtime variable context.

    Returns:
        The sum, or ``None`` if either operand is missing.
    """
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
    """Subtract two numeric values resolved from *spec* and *context*.

    Args:
        spec: Operation spec with ``path`` and either ``value`` or
            ``value_path``.
        context: Runtime variable context.

    Returns:
        The difference, or ``None`` if either operand is missing.
    """
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
    """Multiply two numeric values resolved from *spec* and *context*.

    Args:
        spec: Operation spec with ``path`` and either ``value`` or
            ``value_path``.
        context: Runtime variable context.

    Returns:
        The product, or ``None`` if either operand is missing.
    """
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
    """Add an ISO 8601 duration to the current workflow time.

    Reads ``__now__`` from *context* (ISO string or ``datetime``) and a
    duration string from the path given by ``spec["value_path"]``.

    Args:
        spec: Operation spec with ``value_path`` pointing to a duration
            string (e.g. ``"PT30M"``).
        context: Runtime variable context containing ``__now__``.

    Returns:
        The resulting datetime as an ISO 8601 string, or ``None`` if
        ``__now__`` or the duration is missing.
    """
    now_raw = context.get("__now__")
    if now_raw is None:
        return None
    now = datetime.fromisoformat(now_raw) if isinstance(now_raw, str) else now_raw
    dur_path = spec.get("value_path")
    if dur_path:
        dur_str = resolve_path(context, dur_path)
        if dur_str:
            dt = now + parse_duration(dur_str)
            return dt.isoformat()
    return None


@operation(
    description="Add an offset to a date.",
    schema="binary_date",
    example={"op": "date_add", "path": "start_date", "value": "14 days"},
)
def date_add(spec: dict, context: dict) -> str | None:
    """Add a human-readable offset to a date string."""
    base_date = resolve_path(context, spec.get("path", ""))
    offset_str = spec.get("value")
    return apply_date_math(base_date, offset_str, op_type="add")


@operation(
    description="Subtract an offset from a date.",
    schema="binary_date",
    example={"op": "date_subtract", "path": "due_date", "value": "7 days"},
)
def date_subtract(spec: dict, context: dict) -> str | None:
    """Subtract a human-readable offset from a date string."""
    base_date = resolve_path(context, spec.get("path", ""))
    offset_str = spec.get("value")
    return apply_date_math(base_date, offset_str, op_type="subtract")


@operation(
    description="Append a value to a list.",
    schema="list_append",
    example={"op": "append", "path": "selected_items", "value": "photo_update"},
)
def append(spec: dict, context: dict) -> list:
    """Append a value to a list, returning the new list without mutation.

    Reads the current list from ``spec["path"]`` in *context* and appends
    the value resolved from ``spec["value"]`` or ``spec["value_path"]``.
    Rejects non-list targets and ``None`` values to match the safety
    guarantees of ``append_path``.

    Args:
        spec: Operation spec with ``path`` and either ``value`` or
            ``value_path``.
        context: Runtime variable context.

    Returns:
        A new list containing the existing elements plus the appended value.

    Raises:
        ValueError: If the target is not a list or the resolved value is
            ``None``.
    """
    path = spec.get("path", "")
    existing = resolve_path(context, path)
    if existing is not None and not isinstance(existing, list):
        raise ValueError(
            f"Append target '{path}' must be a list or unset, got {type(existing).__name__}"
        )
    value = (
        resolve_path(context, spec["value_path"])
        if "value_path" in spec
        else spec.get("value")
    )
    if value is None:
        raise ValueError(f"Append operation for '{path}' resolved no value")
    return [*(existing or []), value]


# ---------------------------------------------------------------------------
# Predicate operations — thin wrappers around src.predicates.evaluate()
# ---------------------------------------------------------------------------

_PREDICATE_OPS = [
    ("eq", "Test equality of two values."),
    ("lt", "Test whether a value is less than another."),
    ("lte", "Test whether a value is less than or equal to another."),
    ("gt", "Test whether a value is greater than another."),
    ("gte", "Test whether a value is greater than or equal to another."),
    ("is_true", "Test whether a value is truthy."),
    ("is_false", "Test whether a value is falsy."),
    ("not_empty", "Test whether a value is populated."),
    ("contains", "Test whether a value contains another value."),
    ("and", "Logical AND across multiple conditions."),
    ("or", "Logical OR across multiple conditions."),
    ("not", "Logical negation of a condition."),
    ("date_before", "Test whether a date is before another date."),
    ("before_now", "Test whether a date is before the current time."),
    ("date_diff_greater_than", "Test whether a date difference exceeds a threshold."),
]

for _name, _desc in _PREDICATE_OPS:
    def _make_pred(op_name: str):
        """Build a predicate operation function bound to *op_name*."""
        def pred(spec: dict[str, Any], context: dict[str, Any]) -> bool:
            """Evaluate a predicate condition against *context*."""
            condition = Condition.model_validate(spec)
            return evaluate(condition=condition, context=context)
        pred.__name__ = op_name
        return pred

    operation(description=_desc, schema="predicate")(
        _make_pred(_name)
    )

del _name, _desc


# ---------------------------------------------------------------------------
# Internal helpers (not registered)
# ---------------------------------------------------------------------------


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
    """Parse a date value into a ``datetime``, trying several common formats.

    Args:
        val: A ``datetime`` instance or a string in ``YYYY-MM-DD``,
            ``DD/MM/YYYY``, or ISO 8601 datetime format.

    Returns:
        The parsed ``datetime``, or ``None`` if *val* is falsy or no
        format matches.
    """
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
