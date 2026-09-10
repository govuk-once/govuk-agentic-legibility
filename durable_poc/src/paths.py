"""Path resolution, interpolation, and duration parsing."""

import re
from datetime import timedelta
from typing import Any

# Matches ISO 8601 Durations requiring at least one populated unit
DURATION_RE = re.compile(
    r"^P(?=.)(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def resolve_path(context: dict[str, Any], path: str) -> Any:
    """Resolve a dot-separated path against a context dictionary."""
    if not path:
        return None
    parts = path.split(".")
    current = context
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            return None
    return current


def set_path(context: dict[str, Any], path: str, value: Any) -> None:
    """Mutate context to set a value at a dot-separated path, creating nested dicts or lists as needed."""
    parts = path.split(".")
    current = context
    for i, part in enumerate(parts[:-1]):
        next_part = parts[i + 1]

        if isinstance(current, dict):
            if part not in current:
                current[part] = [] if next_part.isdigit() else {}
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            while len(current) <= idx:
                current.append({})
            current = current[idx]

    last_part = parts[-1]
    if isinstance(current, dict):
        current[last_part] = value
    elif isinstance(current, list) and last_part.isdigit():
        idx = int(last_part)
        while len(current) <= idx:
            current.append(None)
        current[idx] = value


def interpolate(template: str, context: dict[str, Any]) -> str:
    """Replace {{path.to.var}} in strings with resolved context values."""

    def replacer(match: re.Match[str]) -> str:
        val = resolve_path(context, match.group(1).strip())
        return str(val) if val is not None else ""

    return re.sub(r"\{\{(.*?)\}\}", replacer, template)


def resolve_dict(data: Any, context: dict[str, Any]) -> Any:
    """Recursively traverse a dict, replacing {"$": "path"} with resolved values."""
    if isinstance(data, dict):
        if len(data) == 1 and "$" in data:
            return resolve_path(context, data["$"])
        return {k: resolve_dict(v, context) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_dict(item, context) for item in data]
    return data


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
