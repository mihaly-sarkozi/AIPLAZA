# backend/core/infrastructure/cache/redis_client.py
# Feladat: Natív Redis kliens lazy létrehozását és lifecycle kezelését adja. Auth allowlist, rate limit, permission-change store és demo signup abuse control olyan Redis műveleteihez használható, amelyek nem férnek bele a CacheBackend get/set/delete contractba. Thread lockkal védett singleton, amelyet app shutdownkor a lifespan zár le.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import threading
from typing import Any

_redis_client: Any = None
_redis_client_lock = threading.Lock()

# Létrehoz egy Redis klientet a Redis URL alapján
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

# Leállítja a Redis kapcsolatot
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
