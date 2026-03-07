# apps/core/cache – központi cache (tenant, user, permissions_changed); Redis vagy memory.
from apps.core.cache.ports import CacheBackend
from apps.core.cache.memory_backend import MemoryCacheBackend
from apps.core.cache.redis_backend import RedisCacheBackend

__all__ = ["CacheBackend", "MemoryCacheBackend", "RedisCacheBackend", "get_cache", "set_cache"]

# Kulcs prefixek és TTL (másodperc)
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

_cache: CacheBackend | None = None


def get_cache() -> CacheBackend:
    """Központi cache backend (container állítja be; különben memory fallback)."""
    global _cache
    if _cache is None:
        from config.settings import settings
        if getattr(settings, "redis_url", None) and str(settings.redis_url).strip():
            import redis
            _cache = RedisCacheBackend(redis.from_url(settings.redis_url, decode_responses=True))
        else:
            _cache = MemoryCacheBackend()
    return _cache


def set_cache(backend: CacheBackend | None) -> None:
    """Teszt / DI: cache backend felülírása."""
    global _cache
    _cache = backend
