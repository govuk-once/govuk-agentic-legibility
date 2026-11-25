"""Path resolution, interpolation, and duration parsing."""

import re
from typing import Any


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


def append_path(context: dict[str, Any], path: str, value: Any) -> None:
    """Append one typed value without mutating an existing accumulator list.

    An absent or null target starts an empty list.  Rejecting a missing value
    avoids accidentally recording an answer that was never submitted.
    """
    if not path or any(not part for part in path.split(".")):
        raise ValueError("Append target must be a non-empty dotted path")
    existing = resolve_path(context, path)
    if existing is not None and not isinstance(existing, list):
        raise ValueError(f"Append target '{path}' must be a list or unset, got {type(existing).__name__}")
    if value is None:
        raise ValueError(f"Append operation for '{path}' resolved no value")
    set_path(context, path, [*(existing or []), value])


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

