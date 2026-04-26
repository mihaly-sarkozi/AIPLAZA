from __future__ import annotations

from sqlalchemy import text

from core.capabilities.cache import get_cache
from core.kernel.clock import utc_now


class LifecycleProbeRepository:
    """Infrastruktúra szintű health check szondák.

    background_worker_probe:
      Ha None → process-local OutboxWorker nincs → "disabled" eredmény
      (pl. INSTANCE_ROLE=web, ahol a feldolgozás külön worker-processben fut).
      Ha OutboxWorker-t kap → lekérdezi az állapotát (running / stopped / stb.).
    """

    def __init__(
        self,
        session_factory,
        *,
        cache_backend=None,
        # Opcionális OutboxWorker példány (NEM az event_channel).
        # web módban None → "disabled" → ready=True (elfogadott állapot).
        background_worker_probe=None,
    ):
        self._session_factory = session_factory
        self._cache_backend = cache_backend or get_cache()
        self._background_worker_probe = background_worker_probe

    def check_database(self) -> str:
        with self._session_factory() as db:
            db.execute(text("SELECT 1"))
        return "ok"

    def check_cache(self) -> str:
        cache = self._cache_backend
        probe_key = "__platform_readiness_probe__"
        probe_value = utc_now().isoformat()
        cache.set(probe_key, probe_value, 5)
        cached = cache.get(probe_key)
        cache.delete(probe_key)
        if cached != probe_value:
            raise RuntimeError("cache_probe_mismatch")
        return "ok"

    def check_background_worker(self) -> str:
        """Lekérdezi a háttérfeldolgozó állapotát.

        Visszatérési értékek:
          disabled    – nincs worker ebben a processben (INSTANCE_ROLE=web, vagy nincs konfigurálva)
          running     – worker szál fut (combined mód)
          stopped     – worker szál leállt (hiba jelzés)
          not_started – worker még nem indult (átmeneti állapot)

        INSTANCE_ROLE=web esetén mindig "disabled" – a feldolgozás külön worker-processben fut.
        """
        # Web-only processben a background worker nem fut ebben a processben
        try:
            from core.kernel.config.instance_role import InstanceRole, get_instance_role
            if get_instance_role() == InstanceRole.WEB:
                return "disabled"
        except Exception:
            pass  # konfiguráció még nem töltődött be – folytassuk normálisan

        probe = self._background_worker_probe
        if probe is None:
            return "disabled"

        # Duck typing: OutboxWorker (is_running + status) vagy kompatibilis interfész
        if hasattr(probe, "is_running") and probe.is_running():
            return "running"
        if hasattr(probe, "status"):
            return str(probe.status())
        return "unknown"
