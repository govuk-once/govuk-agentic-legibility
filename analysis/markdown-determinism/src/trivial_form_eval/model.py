from typing import Any


def litellm_completion(**kwargs: Any) -> Any:
    from litellm import completion

    return completion(**kwargs)
