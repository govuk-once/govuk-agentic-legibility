"""Shared types for server-driven journey execution."""

from collections.abc import Mapping
from typing import Any, TypeAlias

JsonObject: TypeAlias = dict[str, Any]
ReadOnlyJsonObject: TypeAlias = Mapping[str, Any]
