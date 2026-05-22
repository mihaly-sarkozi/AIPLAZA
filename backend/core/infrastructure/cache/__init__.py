# backend/core/infrastructure/cache/__init__.py
# Feladat: A közös cache infrastruktúra exportfelülete, kulcsképző helperkészlete és backend factoryja. Tenant, domain, user és permission cache kulcsokat/TTL-eket definiál, lazy módon Redis vagy memory backendet választ, és tesztekhez felülírható singleton cache-t tart. Core infrastruktúra adapter több modul cache igényéhez.
# Sárközi Mihály - 2026.05.21
"""Cache package.

Eager exportok (pure Python, nincs adapter-függőség):
  - Kulcs prefix konstansok és TTL értékek
  - Key builder helper függvények (tenant_cache_key, stb.)
  - get_cache() / set_cache() – backend factory (lazy belül)

Lazy exportok (__getattr__, csak igényléskor töltődnek be):
  - CacheBackend      – ports.py Protocol
  - MemoryCacheBackend – memory_backend.py
  - RedisCacheBackend  – redis_backend.py
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.infrastructure.cache.ports import CacheBackend
    from core.infrastructure.cache.memory_backend import MemoryCacheBackend
    from core.infrastructure.cache.redis_backend import RedisCacheBackend

# ── Kulcs prefixek és TTL (másodperc) – pure Python konstansok ──────────────
TENANT_KEY_PREFIX = "tenant:"
TENANT_TTL_SEC = 60
TENANT_STATUS_KEY_PREFIX = "tenant_status:"
TENANT_STATUS_TTL_SEC = 120
TENANT_CONFIG_KEY_PREFIX = "tenant_config:"
TENANT_CONFIG_TTL_SEC = 300
DOMAIN2TENANT_KEY_PREFIX = "domain2tenant:"
DOMAIN2TENANT_TTL_SEC = 300
USER_KEY_PREFIX = "user:"
USER_TTL_SEC = 60
PERMISSIONS_CHANGED_KEY_PREFIX = "pc:"
PERMISSIONS_CHANGED_TTL_SEC = 120


# ── Cache kulcs builder-ek ────────────────────────────────────────────────────

def tenant_cache_key(slug: str) -> str:
    return f"{TENANT_KEY_PREFIX}{slug}"


def tenant_status_cache_key(slug: str) -> str:
    return f"{TENANT_STATUS_KEY_PREFIX}{slug}"


def tenant_config_cache_key(slug: str) -> str:
    return f"{TENANT_CONFIG_KEY_PREFIX}{slug}"


def domain2tenant_cache_key(host: str) -> str:
    """Host (domain, normalizált) → cache kulcs a tenant slug/id tárolásához."""
    return f"{DOMAIN2TENANT_KEY_PREFIX}{host}"


def user_cache_key(tenant_slug: str | None, user_id: int) -> str:
    t = tenant_slug if tenant_slug is not None else ""
    return f"{USER_KEY_PREFIX}{t}:{user_id}"


def permissions_changed_cache_key(tenant_slug: str | None, user_id: int) -> str:
    t = tenant_slug if tenant_slug is not None else ""
    return f"{PERMISSIONS_CHANGED_KEY_PREFIX}{t}:{user_id}"


# ── Backend singleton ─────────────────────────────────────────────────────────

_cache: "CacheBackend | None" = None


def get_cache() -> "CacheBackend":
    """Központi cache backend (container állítja be; különben memory fallback)."""
    global _cache
    if _cache is None:
        from core.kernel.config.config_loader import settings

        if getattr(settings, "redis_url", None) and str(settings.redis_url).strip():
            import redis
            from core.infrastructure.cache.redis_backend import RedisCacheBackend

            _cache = RedisCacheBackend(redis.from_url(settings.redis_url, decode_responses=True))
        else:
            from core.infrastructure.cache.memory_backend import MemoryCacheBackend

            _cache = MemoryCacheBackend()
    return _cache


def set_cache(backend: "CacheBackend | None") -> None:
    """Teszt / DI: cache backend felülírása."""
    global _cache
    _cache = backend


# ── Lazy class exportok ───────────────────────────────────────────────────────

_LAZY_CLASSES = {
    "CacheBackend": ("core.infrastructure.cache.ports", "CacheBackend"),
    "MemoryCacheBackend": ("core.infrastructure.cache.memory_backend", "MemoryCacheBackend"),
    "RedisCacheBackend": ("core.infrastructure.cache.redis_backend", "RedisCacheBackend"),
}


def __getattr__(name: str):
    if name in _LAZY_CLASSES:
        module_path, attr = _LAZY_CLASSES[name]
        import importlib

        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    raise AttributeError(name)


__all__ = [
    # Konstansok
    "TENANT_KEY_PREFIX", "TENANT_TTL_SEC",
    "TENANT_STATUS_KEY_PREFIX", "TENANT_STATUS_TTL_SEC",
    "TENANT_CONFIG_KEY_PREFIX", "TENANT_CONFIG_TTL_SEC",
    "DOMAIN2TENANT_KEY_PREFIX", "DOMAIN2TENANT_TTL_SEC",
    "USER_KEY_PREFIX", "USER_TTL_SEC",
    "PERMISSIONS_CHANGED_KEY_PREFIX", "PERMISSIONS_CHANGED_TTL_SEC",
    # Key builder-ek
    "tenant_cache_key",
    "tenant_status_cache_key",
    "tenant_config_cache_key",
    "domain2tenant_cache_key",
    "user_cache_key",
    "permissions_changed_cache_key",
    # Backend factory
    "get_cache",
    "set_cache",
    # Lazy class exportok
    "CacheBackend",
    "MemoryCacheBackend",
    "RedisCacheBackend",
]
