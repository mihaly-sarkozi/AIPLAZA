# Központi Redis kliens: allowlist, rate limit, cache.

from __future__ import annotations

import threading
from typing import Any

_redis_client: Any = None
_redis_client_lock = threading.Lock()


def get_redis():
    """Lazy Redis kliens (decode_responses=True). Nincs redis_url -> None."""
    global _redis_client
    from core.kernel.config.config_loader import settings
    if not getattr(settings, "redis_url", None) or not str(settings.redis_url).strip():
        return None
    with _redis_client_lock:
        if _redis_client is None:
            import redis
            _redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
        return _redis_client


def close_redis() -> None:
    """Lifespan shutdown: Redis kapcsolat bezárása."""
    global _redis_client
    with _redis_client_lock:
        if _redis_client is not None:
            try:
                _redis_client.close()
            except Exception:
                pass
            _redis_client = None
