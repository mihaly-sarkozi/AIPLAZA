# backend/core/kernel/interface/routing.py
# Feladat: A modulok route regisztrációs szerződését definiálja. A RouteRegistration dataclass egységesen írja le, melyik FastAPI router milyen prefixszel és taggel kerüljön az appba. Core public interface, amelyet app modulok és az app manifest route registry közösen használnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RouteRegistration:
    router: Any
    prefix: str = "/api"
    tags: tuple[str, ...] = ()


__all__ = ["RouteRegistration"]

