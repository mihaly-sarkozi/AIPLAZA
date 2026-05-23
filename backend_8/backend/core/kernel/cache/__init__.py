# backend/core/kernel/cache/__init__.py
# Feladat: Publikus kernel cache/Redis segedfuggvenyek routerek es service-ek
# szamara. Az infrastruktura Redis kliens kozvetlen importjat rejti el.

from __future__ import annotations


def redis_configured() -> bool:
    from core.infrastructure.cache.redis_client import get_redis

    return get_redis() is not None


__all__ = ["redis_configured"]
