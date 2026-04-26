"""Route registration contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RouteRegistration:
    router: Any
    prefix: str = "/api"
    tags: tuple[str, ...] = ()


__all__ = ["RouteRegistration"]

