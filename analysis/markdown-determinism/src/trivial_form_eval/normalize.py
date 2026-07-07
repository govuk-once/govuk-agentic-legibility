from collections.abc import Mapping
from typing import Any


def get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def serialise_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        return [serialise_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): serialise_safe(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return serialise_safe(value.model_dump())
    if hasattr(value, "dict"):
        return serialise_safe(value.dict())
    return repr(value)


def response_usage(response: Any) -> Any:
    return serialise_safe(get_value(response, "usage"))


def response_cost(response: Any) -> Any:
    for key in ("_hidden_params", "hidden_params"):
        params = get_value(response, key)
        if params:
            cost = get_value(params, "response_cost")
            if cost is not None:
                return cost
    return get_value(response, "response_cost")


def first_choice(response: Any) -> Any:
    choices = get_value(response, "choices", [])
    return choices[0] if choices else None


def message_from_choice(choice: Any) -> Any:
    return get_value(choice, "message") if choice is not None else None


def finish_reason(choice: Any) -> Any:
    return get_value(choice, "finish_reason") if choice is not None else None


def infer_provider(response: Any, requested_model: str) -> str | None:
    params = get_value(response, "_hidden_params") or get_value(response, "hidden_params")
    provider = get_value(params, "custom_llm_provider") if params else None
    if provider:
        return provider
    return requested_model.split("/", 1)[0] if "/" in requested_model else None
