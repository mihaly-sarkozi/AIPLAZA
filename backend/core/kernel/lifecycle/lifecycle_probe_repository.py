# backend/core/kernel/lifecycle/lifecycle_probe_repository.py
# Feladat: Infrastruktúra szintű lifecycle probe-okat futtat. Adatbázis SELECT 1, cache/Redis roundtrip, object storage config, migration státusz és background worker állapot alapján ad readiness státuszokat. Kernel lifecycle adapter a DB/cache/worker/deployment ellenőrzésekhez.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from sqlalchemy import text

from core.infrastructure.cache.redis_client import get_redis
from core.kernel.config.environment import is_deployed_env, normalize_app_env
from core.kernel.config.config_loader import settings
from core.infrastructure.cache import get_cache
from core.kernel.events.outbox import OutboxHealthService, PlatformEventOutboxRepository
from core.kernel.runtime.clock import utc_now
from core.modules.tenant.schema.public import public_schema_migration_revisions


class LifecycleProbeRepository:
    """Infrastruktúra szintű health check szondák.

    background_worker_probe:
      Ha None -> process-local OutboxWorker nincs -> "disabled" eredmény
      (pl. INSTANCE_ROLE=web, ahol a feldolgozás külön worker-processben fut).
      Ha OutboxWorker-t kap -> lekérdezi az állapotát (running / stopped / stb.).
    """

    def __init__(
        self,
        session_factory,
        *,
        cache_backend=None,
        # Opcionális OutboxWorker példány (NEM az event_channel).
        # web módban None -> "disabled" -> ready=True (elfogadott állapot).
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

    def check_redis(self) -> str:
        env = normalize_app_env()
        redis_client = get_redis()
        if redis_client is None:
            if is_deployed_env(env):
                raise RuntimeError("redis_required_but_not_configured")
            return "optional"
        if not bool(redis_client.ping()):
            raise RuntimeError("redis_ping_failed")
        return "ok"

    def check_object_storage(self) -> str:
        env = normalize_app_env()
        enabled = bool(getattr(settings, "object_storage_enabled", True))
        provider = str(getattr(settings, "object_storage_provider", "") or "").strip().lower()
        endpoint = str(getattr(settings, "object_storage_endpoint", "") or "").strip()
        bucket = str(getattr(settings, "object_storage_bucket", "") or "").strip()
        if not enabled:
            if is_deployed_env(env):
                raise RuntimeError("object_storage_required_but_disabled")
            return "disabled"
        if provider != "s3_compatible":
            raise RuntimeError("object_storage_provider_invalid")
        if not endpoint or not bucket:
            if is_deployed_env(env):
                raise RuntimeError("object_storage_required_config_missing")
            return "configured_partial"
        from shared.object_storage.service import get_object_storage

        storage = get_object_storage()
        build_key = getattr(storage, "build_key", None)
        if not callable(build_key):
            raise RuntimeError("object_storage_adapter_invalid")
        build_key("__readiness__")
        return "ok"

    def check_migrations(self) -> str:
        expected = set(public_schema_migration_revisions())
        with self._session_factory() as db:
            exists = db.execute(
                text(
                    """
                    SELECT to_regclass('public.platform_schema_migrations')
                    """
                )
            ).scalar()
            if not exists:
                raise RuntimeError("migration_table_missing")
            rows = db.execute(text("SELECT revision FROM public.platform_schema_migrations")).fetchall()
        applied = {str(row[0]) for row in rows}
        missing = sorted(expected - applied)
        if missing:
            raise RuntimeError(f"migrations_missing:{','.join(missing)}")
        return "ok"

    @staticmethod
    def _email_feature_active() -> bool:
        demo_signups_enabled = bool(getattr(settings, "demo_signups_enabled", True))
        require_email_verification = bool(getattr(settings, "demo_signup_require_email_verification", True))
        admin_alert_email = str(getattr(settings, "platform_admin_login_alert_email", "") or "").strip()
        return (demo_signups_enabled and require_email_verification) or bool(admin_alert_email)

    def check_smtp(self) -> str:
        if not self._email_feature_active():
            return "optional"
        if not is_deployed_env(normalize_app_env()):
            return "optional"
        host = str(getattr(settings, "smtp_host", "") or "").strip()
        user = str(getattr(settings, "smtp_user", "") or "").strip()
        password = str(getattr(settings, "smtp_password", "") or "").strip()
        from_email = str(getattr(settings, "smtp_from_email", "") or "").strip()
        from_name = str(getattr(settings, "smtp_from_name", "") or "").strip()
        if not host or not user or not password or not from_email or not from_name:
            raise RuntimeError("smtp_required_config_missing")
        return "ok"

    def check_url_ingest_isolation_guard(self) -> str:
        if not bool(getattr(settings, "knowledge_url_ingest_enabled", False)):
            return "disabled"
        requires_isolated_worker = bool(getattr(settings, "knowledge_url_ingest_requires_isolated_worker", True))
        worker_isolated = bool(getattr(settings, "knowledge_url_ingest_worker_isolated", False))
        if not requires_isolated_worker:
            raise RuntimeError("url_ingest_requires_isolated_worker_disabled")
        if not worker_isolated:
            raise RuntimeError("url_ingest_worker_not_isolated")
        return "ok"

    def check_outbox_queue(self) -> str:
        snapshot = self.outbox_queue_snapshot()
        required_keys = {"pending", "running", "failed", "dead_letter", "stuck_leases"}
        if not required_keys.issubset(set(snapshot.keys())):
            raise RuntimeError("outbox_snapshot_incomplete")
        return "ok"

    def check_background_worker(self) -> str:
        """Lekérdezi a háttérfeldolgozó állapotát.

        Visszatérési értékek:
          disabled    - nincs worker ebben a processben (INSTANCE_ROLE=web, vagy nincs konfigurálva)
          running     - worker szál fut (combined mód)
          stopped     - worker szál leállt (hiba jelzés)
          not_started - worker még nem indult (átmeneti állapot)

        INSTANCE_ROLE=web esetén mindig "disabled" - a feldolgozás külön worker-processben fut.
        """
        # Web-only processben a background worker nem fut ebben a processben
        try:
            from core.kernel.runtime.instance_role import InstanceRole, get_instance_role

            if get_instance_role() == InstanceRole.WEB:
                return "disabled"
        except Exception:
            pass  # konfiguráció még nem töltődött be - folytassuk normálisan

        probe = self._background_worker_probe
        if probe is None:
            return "disabled"

        # Duck typing: OutboxWorker (is_running + status) vagy kompatibilis interfész
        if hasattr(probe, "is_running") and probe.is_running():
            return "running"
        if hasattr(probe, "status"):
            return str(probe.status())
        return "unknown"

    def outbox_queue_snapshot(self) -> dict[str, object]:
        repo = PlatformEventOutboxRepository(self._session_factory)
        snapshot = OutboxHealthService(repo).queue_snapshot()
        return {
            "pending": int(snapshot.get("pending_jobs") or 0),
            "running": int(snapshot.get("running_jobs") or 0),
            "failed": int(snapshot.get("failed_jobs") or 0),
            "dead_letter": int(snapshot.get("dead_letter_jobs") or 0),
            "stuck_leases": int(snapshot.get("stuck_leases") or 0),
            "oldest_pending_seconds": float(snapshot.get("oldest_pending_age_seconds") or 0.0),
            "average_attempts": float(snapshot.get("average_attempt_count") or 0.0),
            "worker_status": str(self.check_background_worker() or "unknown"),
            "worker_heartbeat_at": snapshot.get("worker_heartbeat_at"),
            "worker_heartbeat_age_seconds": (
                float(snapshot.get("worker_heartbeat_age_seconds"))
                if snapshot.get("worker_heartbeat_age_seconds") is not None
                else None
            ),
        }
