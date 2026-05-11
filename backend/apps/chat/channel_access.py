from __future__ import annotations

import hashlib
import secrets
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import and_, desc, func, text

from apps.chat.channel_models import (
    ChannelCredentialORM,
    ChannelFeedbackEventORM,
    ChannelUsageEventORM,
)
from core.kernel.config.environment import get_app_env
from core.kernel.config import app_settings
from core.kernel.db.model_bases import PublicBase
from core.kernel.security.rate_limit import get_rate_limit_redis


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _period_key(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


@dataclass(frozen=True)
class ChannelPrincipal:
    tenant_id: int
    credential_id: int
    channel_type: str
    allowed_kb_uuids: list[str]
    daily_limit: int
    per_minute_limit: int
    allowed_origins: list[str]


class ChannelAccessRepository:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]) -> None:
        self._sf = session_factory
        self._quota_lock = threading.RLock()
        self._quota_fallback_counters: dict[str, int] = {}

    @staticmethod
    def _normalize_list(values: list[str] | None) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in values or []:
            value = str(item or "").strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(value)
        return out

    @classmethod
    def _normalize_widget_origin(cls, value: str) -> str:
        text_value = str(value or "").strip().lower()
        if not text_value:
            raise ValueError("Az allowed_origins nem tartalmazhat üres elemet.")
        if "*" in text_value:
            raise ValueError("Wildcard origin nem engedélyezett widget credentialnél.")
        if "://" not in text_value:
            text_value = f"https://{text_value}"
        parsed = urlparse(text_value)
        scheme = str(parsed.scheme or "").strip().lower()
        host = str(parsed.hostname or "").strip().lower()
        port = parsed.port
        if scheme not in {"http", "https"}:
            raise ValueError("Widget origin csak http vagy https lehet.")
        if not host:
            raise ValueError("Widget origin host kötelező.")
        if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("Widget origin csak protocol+host formátum lehet (útvonal nélkül).")
        if parsed.username or parsed.password:
            raise ValueError("Widget origin nem tartalmazhat userinfo részt.")
        if ":" in host and not host.startswith("["):
            # Nyers IPv6 vagy hibás host; urlparse hostname ilyenkor már normalizál.
            raise ValueError("Widget origin host formátuma érvénytelen.")
        if port is not None:
            return f"{scheme}://{host}:{int(port)}"
        return f"{scheme}://{host}"

    @classmethod
    def _normalize_widget_origins(cls, values: list[str] | None) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in values or []:
            normalized = cls._normalize_widget_origin(str(item or ""))
            if normalized in seen:
                continue
            seen.add(normalized)
            out.append(normalized)
        return out

    @staticmethod
    def _hash_secret(secret: str) -> str:
        pepper = str(getattr(app_settings, "jwt_secret", "") or "aiplaza").strip()
        payload = f"{pepper}:{secret}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _origin_value(origin: str | None) -> str:
        text_value = str(origin or "").strip()
        if not text_value:
            return ""
        try:
            parsed = urlparse(text_value)
            scheme = str(parsed.scheme or "").strip().lower()
            host = str(parsed.hostname or "").strip().lower()
            port = parsed.port
            if scheme not in {"http", "https"} or not host:
                return ""
            if port is not None:
                return f"{scheme}://{host}:{int(port)}"
            return f"{scheme}://{host}"
        except Exception:
            return ""

    def ensure_storage(self) -> None:
        tables = (
            ChannelCredentialORM.__table__,
            ChannelUsageEventORM.__table__,
            ChannelFeedbackEventORM.__table__,
        )
        PublicBase.metadata.create_all(bind=self._sf.engine, tables=list(tables))
        with self._sf.engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_credentials_key_prefix ON public.channel_credentials(key_prefix)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_feedback_events_trace_id ON public.channel_feedback_events(trace_id)"))
            commit = getattr(conn, "commit", None)
            if callable(commit):
                commit()

    def create_credential(
        self,
        *,
        tenant_id: int,
        channel_type: str,
        name: str,
        allowed_kb_uuids: list[str],
        daily_limit: int,
        per_minute_limit: int,
        allowed_origins: list[str],
        expires_at: datetime | None,
        created_by: int | None,
    ) -> dict[str, Any]:
        prefix = f"ck_{secrets.token_urlsafe(6)}".lower()
        secret_tail = secrets.token_urlsafe(24)
        secret_value = f"{prefix}.{secret_tail}"
        normalized_channel_type = str(channel_type or "widget").strip().lower()
        normalized_allowed_origins = (
            self._normalize_widget_origins(allowed_origins)
            if normalized_channel_type == "widget"
            else self._normalize_list(allowed_origins)
        )
        if normalized_channel_type == "widget" and not normalized_allowed_origins:
            raise ValueError("Widget credential esetén az allowed_origins megadása kötelező.")
        row = ChannelCredentialORM(
            tenant_id=tenant_id,
            channel_type=normalized_channel_type,
            name=str(name or "Unnamed").strip() or "Unnamed",
            key_prefix=prefix,
            secret_hash=self._hash_secret(secret_value),
            status="active",
            allowed_kb_uuids=self._normalize_list(allowed_kb_uuids),
            daily_limit=max(1, int(daily_limit)),
            per_minute_limit=max(1, int(per_minute_limit)),
            allowed_origins=normalized_allowed_origins,
            expires_at=expires_at,
            created_by=created_by,
            updated_by=created_by,
        )
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            db.add(row)
            db.commit()
            db.refresh(row)
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "channel_type": row.channel_type,
            "name": row.name,
            "key_prefix": row.key_prefix,
            "secret": secret_value,
            "status": row.status,
            "allowed_kb_uuids": list(row.allowed_kb_uuids or []),
            "daily_limit": int(row.daily_limit or 0),
            "per_minute_limit": int(row.per_minute_limit or 0),
            "allowed_origins": list(row.allowed_origins or []),
            "expires_at": row.expires_at,
            "created_at": row.created_at,
        }

    def list_credentials(self, *, tenant_id: int) -> list[dict[str, Any]]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            rows = (
                db.query(ChannelCredentialORM)
                .filter(ChannelCredentialORM.tenant_id == tenant_id)
                .order_by(ChannelCredentialORM.id.desc())
                .all()
            )
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": row.id,
                    "tenant_id": row.tenant_id,
                    "channel_type": row.channel_type,
                    "name": row.name,
                    "key_prefix": row.key_prefix,
                    "status": row.status,
                    "allowed_kb_uuids": list(row.allowed_kb_uuids or []),
                    "daily_limit": int(row.daily_limit or 0),
                    "per_minute_limit": int(row.per_minute_limit or 0),
                    "allowed_origins": list(row.allowed_origins or []),
                    "expires_at": row.expires_at,
                    "last_used_at": row.last_used_at,
                    "created_at": row.created_at,
                    "revoked_at": row.revoked_at,
                }
            )
        return out

    def update_policy(
        self,
        *,
        tenant_id: int,
        credential_id: int,
        allowed_kb_uuids: list[str] | None,
        daily_limit: int | None,
        per_minute_limit: int | None,
        allowed_origins: list[str] | None,
        updated_by: int | None,
        expires_at: datetime | None,
    ) -> dict[str, Any] | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(ChannelCredentialORM)
                .filter(
                    ChannelCredentialORM.id == credential_id,
                    ChannelCredentialORM.tenant_id == tenant_id,
                )
                .first()
            )
            if row is None:
                return None
            if allowed_kb_uuids is not None:
                row.allowed_kb_uuids = self._normalize_list(allowed_kb_uuids)
            if daily_limit is not None:
                row.daily_limit = max(1, int(daily_limit))
            if per_minute_limit is not None:
                row.per_minute_limit = max(1, int(per_minute_limit))
            if allowed_origins is not None:
                if str(row.channel_type or "widget").strip().lower() == "widget":
                    normalized_allowed_origins = self._normalize_widget_origins(allowed_origins)
                    if not normalized_allowed_origins:
                        raise ValueError("Widget credential esetén az allowed_origins nem lehet üres.")
                    row.allowed_origins = normalized_allowed_origins
                else:
                    row.allowed_origins = self._normalize_list(allowed_origins)
            row.expires_at = expires_at
            row.updated_by = updated_by
            row.updated_at = _utcnow()
            db.commit()
            db.refresh(row)
            return {
                "id": row.id,
                "allowed_kb_uuids": list(row.allowed_kb_uuids or []),
                "daily_limit": int(row.daily_limit or 0),
                "per_minute_limit": int(row.per_minute_limit or 0),
                "allowed_origins": list(row.allowed_origins or []),
                "expires_at": row.expires_at,
                "updated_at": row.updated_at,
            }

    def revoke_credential(self, *, tenant_id: int, credential_id: int, revoked_by: int | None) -> bool:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(ChannelCredentialORM)
                .filter(
                    ChannelCredentialORM.id == credential_id,
                    ChannelCredentialORM.tenant_id == tenant_id,
                )
                .first()
            )
            if row is None:
                return False
            row.status = "revoked"
            row.revoked_at = _utcnow()
            row.revoked_by = revoked_by
            row.updated_by = revoked_by
            row.updated_at = _utcnow()
            db.commit()
            return True

    def rotate_credential(self, *, tenant_id: int, credential_id: int, rotated_by: int | None) -> dict[str, Any] | None:
        prefix = f"ck_{secrets.token_urlsafe(6)}".lower()
        secret_tail = secrets.token_urlsafe(24)
        secret_value = f"{prefix}.{secret_tail}"
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(ChannelCredentialORM)
                .filter(
                    ChannelCredentialORM.id == credential_id,
                    ChannelCredentialORM.tenant_id == tenant_id,
                )
                .first()
            )
            if row is None:
                return None
            row.key_prefix = prefix
            row.secret_hash = self._hash_secret(secret_value)
            row.status = "active"
            row.revoked_at = None
            row.revoked_by = None
            row.updated_by = rotated_by
            row.updated_at = _utcnow()
            db.commit()
            db.refresh(row)
            return {
                "id": row.id,
                "key_prefix": row.key_prefix,
                "secret": secret_value,
                "updated_at": row.updated_at,
            }

    def authenticate(
        self,
        *,
        tenant_id: int,
        presented_secret: str,
        origin: str | None,
    ) -> ChannelPrincipal | None:
        presented_secret = str(presented_secret or "").strip()
        if not presented_secret or "." not in presented_secret:
            return None
        prefix = presented_secret.split(".", 1)[0].strip().lower()
        if not prefix:
            return None
        now = _utcnow()
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(ChannelCredentialORM)
                .filter(
                    ChannelCredentialORM.tenant_id == tenant_id,
                    ChannelCredentialORM.key_prefix == prefix,
                    ChannelCredentialORM.status == "active",
                )
                .first()
            )
            if row is None:
                return None
            if row.expires_at is not None and row.expires_at <= now:
                return None
            expected_hash = str(row.secret_hash or "")
            incoming_hash = self._hash_secret(presented_secret)
            if not secrets.compare_digest(expected_hash, incoming_hash):
                return None
            allowed_origins = [str(item).lower() for item in (row.allowed_origins or []) if str(item or "").strip()]
            if row.channel_type == "widget":
                if not allowed_origins:
                    return None
                origin_value = self._origin_value(origin)
                if not origin_value or origin_value not in allowed_origins:
                    return None
            row.last_used_at = now
            db.commit()
            return ChannelPrincipal(
                tenant_id=tenant_id,
                credential_id=int(row.id),
                channel_type=str(row.channel_type or "widget"),
                allowed_kb_uuids=[str(item) for item in (row.allowed_kb_uuids or []) if str(item or "").strip()],
                daily_limit=max(1, int(row.daily_limit or 1)),
                per_minute_limit=max(1, int(row.per_minute_limit or 1)),
                allowed_origins=list(row.allowed_origins or []),
            )

    def current_usage(self, *, tenant_id: int, credential_id: int) -> dict[str, int]:
        now = _utcnow()
        day_key = _period_key(now)
        minute_start = now - timedelta(minutes=1)
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            daily_count = (
                db.query(func.count(ChannelUsageEventORM.id))
                .filter(
                    ChannelUsageEventORM.tenant_id == tenant_id,
                    ChannelUsageEventORM.credential_id == credential_id,
                    ChannelUsageEventORM.period_key == day_key,
                    ChannelUsageEventORM.status == "ok",
                )
                .scalar()
                or 0
            )
            minute_count = (
                db.query(func.count(ChannelUsageEventORM.id))
                .filter(
                    ChannelUsageEventORM.tenant_id == tenant_id,
                    ChannelUsageEventORM.credential_id == credential_id,
                    ChannelUsageEventORM.created_at >= minute_start,
                    ChannelUsageEventORM.status == "ok",
                )
                .scalar()
                or 0
            )
        return {"daily": int(daily_count), "minute": int(minute_count)}

    def reserve_usage_slot(
        self,
        *,
        tenant_id: int,
        credential_id: int,
        daily_limit: int,
        per_minute_limit: int,
        session_key: str | None = None,
        session_per_minute_limit: int | None = None,
        session_burst_10s_limit: int | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        now = _utcnow()
        day_key = _period_key(now)
        minute_key = now.strftime("%Y-%m-%dT%H:%M")
        burst_10s_key = str(int(now.timestamp()) // 10)
        normalized_daily_limit = max(1, int(daily_limit or 1))
        normalized_minute_limit = max(1, int(per_minute_limit or 1))
        session_scope = str(session_key or "").strip() or ""
        normalized_session_per_minute_limit = max(1, int(session_per_minute_limit or 1))
        normalized_session_burst_10s_limit = max(1, int(session_burst_10s_limit or 1))
        session_limit_enabled = bool(session_scope and session_per_minute_limit and session_burst_10s_limit)
        fail_closed = bool(getattr(app_settings, "channel_quota_fail_closed_without_redis", True))
        try:
            env = get_app_env()
        except Exception:
            env = "dev"

        redis_client = get_rate_limit_redis()
        if redis_client is None and fail_closed and env == "prod":
            return False, "Channel quota szolgáltatás átmenetileg nem elérhető.", None
        if redis_client is not None:
            day_counter_key = f"quota:channel:day:{tenant_id}:{credential_id}:{day_key}"
            minute_counter_key = f"quota:channel:minute:{tenant_id}:{credential_id}:{minute_key}"
            session_minute_counter_key = (
                f"quota:channel:session:minute:{tenant_id}:{credential_id}:{session_scope}:{minute_key}"
                if session_limit_enabled
                else ""
            )
            session_burst_counter_key = (
                f"quota:channel:session:burst10s:{tenant_id}:{credential_id}:{session_scope}:{burst_10s_key}"
                if session_limit_enabled
                else ""
            )
            try:
                pipe = redis_client.pipeline()
                pipe.incr(day_counter_key, 1)
                pipe.expire(day_counter_key, 3 * 24 * 3600)
                pipe.incr(minute_counter_key, 1)
                pipe.expire(minute_counter_key, 180)
                if session_limit_enabled:
                    pipe.incr(session_minute_counter_key, 1)
                    pipe.expire(session_minute_counter_key, 180)
                    pipe.incr(session_burst_counter_key, 1)
                    pipe.expire(session_burst_counter_key, 60)
                results = pipe.execute()
                day_count = int(results[0] or 0)
                minute_count = int(results[2] or 0)
                session_minute_count = int(results[4] or 0) if session_limit_enabled else 0
                session_burst_count = int(results[6] or 0) if session_limit_enabled else 0
                if (
                    day_count > normalized_daily_limit
                    or minute_count > normalized_minute_limit
                    or (
                        session_limit_enabled
                        and (
                            session_minute_count > normalized_session_per_minute_limit
                            or session_burst_count > normalized_session_burst_10s_limit
                        )
                    )
                ):
                    rollback_pipe = redis_client.pipeline()
                    rollback_pipe.decr(day_counter_key, 1)
                    rollback_pipe.decr(minute_counter_key, 1)
                    if session_limit_enabled:
                        rollback_pipe.decr(session_minute_counter_key, 1)
                        rollback_pipe.decr(session_burst_counter_key, 1)
                    rollback_pipe.execute()
                    if day_count > normalized_daily_limit:
                        return False, "Napi kérdéslimit elérve.", None
                    if minute_count > normalized_minute_limit:
                        return False, "Túl sok kérés rövid idő alatt.", None
                    return False, "Túl sok kérés ebből a munkamenetből rövid idő alatt.", None
                return True, "", {
                    "backend": "redis",
                    "day_counter_key": day_counter_key,
                    "minute_counter_key": minute_counter_key,
                    "session_minute_counter_key": session_minute_counter_key,
                    "session_burst_counter_key": session_burst_counter_key,
                }
            except Exception:
                if fail_closed and env == "prod":
                    return False, "Channel quota szolgáltatás átmenetileg nem elérhető.", None

        day_counter_key = f"quota:channel:day:{tenant_id}:{credential_id}:{day_key}"
        minute_counter_key = f"quota:channel:minute:{tenant_id}:{credential_id}:{minute_key}"
        session_minute_counter_key = (
            f"quota:channel:session:minute:{tenant_id}:{credential_id}:{session_scope}:{minute_key}"
            if session_limit_enabled
            else ""
        )
        session_burst_counter_key = (
            f"quota:channel:session:burst10s:{tenant_id}:{credential_id}:{session_scope}:{burst_10s_key}"
            if session_limit_enabled
            else ""
        )
        with self._quota_lock:
            day_count = int(self._quota_fallback_counters.get(day_counter_key, 0)) + 1
            minute_count = int(self._quota_fallback_counters.get(minute_counter_key, 0)) + 1
            session_minute_count = (
                int(self._quota_fallback_counters.get(session_minute_counter_key, 0)) + 1
                if session_limit_enabled
                else 0
            )
            session_burst_count = (
                int(self._quota_fallback_counters.get(session_burst_counter_key, 0)) + 1
                if session_limit_enabled
                else 0
            )
            if day_count > normalized_daily_limit:
                return False, "Napi kérdéslimit elérve.", None
            if minute_count > normalized_minute_limit:
                return False, "Túl sok kérés rövid idő alatt.", None
            if session_limit_enabled and (
                session_minute_count > normalized_session_per_minute_limit
                or session_burst_count > normalized_session_burst_10s_limit
            ):
                return False, "Túl sok kérés ebből a munkamenetből rövid idő alatt.", None
            self._quota_fallback_counters[day_counter_key] = day_count
            self._quota_fallback_counters[minute_counter_key] = minute_count
            if session_limit_enabled:
                self._quota_fallback_counters[session_minute_counter_key] = session_minute_count
                self._quota_fallback_counters[session_burst_counter_key] = session_burst_count
        return True, "", {
            "backend": "memory",
            "day_counter_key": day_counter_key,
            "minute_counter_key": minute_counter_key,
            "session_minute_counter_key": session_minute_counter_key,
            "session_burst_counter_key": session_burst_counter_key,
        }

    def release_usage_slot(self, reservation: dict[str, Any] | None) -> None:
        if not reservation:
            return
        day_counter_key = str(reservation.get("day_counter_key") or "").strip()
        minute_counter_key = str(reservation.get("minute_counter_key") or "").strip()
        session_minute_counter_key = str(reservation.get("session_minute_counter_key") or "").strip()
        session_burst_counter_key = str(reservation.get("session_burst_counter_key") or "").strip()
        if not day_counter_key or not minute_counter_key:
            return
        backend = str(reservation.get("backend") or "").strip().lower()
        if backend == "redis":
            redis_client = get_rate_limit_redis()
            if redis_client is None:
                return
            try:
                pipe = redis_client.pipeline()
                pipe.decr(day_counter_key, 1)
                pipe.decr(minute_counter_key, 1)
                if session_minute_counter_key:
                    pipe.decr(session_minute_counter_key, 1)
                if session_burst_counter_key:
                    pipe.decr(session_burst_counter_key, 1)
                pipe.execute()
            except Exception:
                return
            return
        with self._quota_lock:
            for key in (
                day_counter_key,
                minute_counter_key,
                session_minute_counter_key,
                session_burst_counter_key,
            ):
                if not key:
                    continue
                current = int(self._quota_fallback_counters.get(key, 0))
                if current <= 1:
                    self._quota_fallback_counters.pop(key, None)
                else:
                    self._quota_fallback_counters[key] = current - 1

    def record_usage(
        self,
        *,
        tenant_id: int,
        credential_id: int,
        channel_type: str,
        status: str,
        question: str,
        kb_uuid: str | None,
        query_run_id: str | None,
        origin: str | None,
        remote_ip: str | None,
        response_ms: float | int | None,
        llm_ms: float | int | None,
        context_build_ms: float | int | None,
        total_ms: float | int | None,
    ) -> None:
        now = _utcnow()
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            db.add(
                ChannelUsageEventORM(
                    tenant_id=tenant_id,
                    credential_id=credential_id,
                    channel_type=str(channel_type or "widget"),
                    period_key=_period_key(now),
                    status=str(status or "ok"),
                    question=str(question or "")[:2000],
                    kb_uuid=str(kb_uuid or "").strip() or None,
                    query_run_id=str(query_run_id or "").strip() or None,
                    response_ms=max(0, int(response_ms or 0)),
                    llm_ms=max(0, int(llm_ms or 0)),
                    context_build_ms=max(0, int(context_build_ms or 0)),
                    total_ms=max(0, int(total_ms or 0)),
                    origin=str(origin or "").strip() or None,
                    remote_ip=str(remote_ip or "").strip() or None,
                )
            )
            db.commit()

    def record_feedback(
        self,
        *,
        tenant_id: int,
        credential_id: int | None,
        channel_type: str,
        query_run_id: str | None,
        trace_id: str | None,
        helpful: bool | None,
        reason: str | None,
        note: str | None,
    ) -> dict[str, Any]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = ChannelFeedbackEventORM(
                tenant_id=tenant_id,
                credential_id=credential_id,
                channel_type=str(channel_type or "widget"),
                query_run_id=str(query_run_id or "").strip() or None,
                trace_id=str(trace_id or "").strip() or None,
                helpful=helpful,
                reason=str(reason or "").strip() or None,
                note=str(note or "").strip() or None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return {"id": row.id, "triage_status": row.triage_status, "created_at": row.created_at}

    def triage_feedback(
        self,
        *,
        tenant_id: int,
        feedback_id: int,
        triage_status: str,
        triage_owner: str | None,
        triage_note: str | None,
        triaged_by: int | None,
    ) -> dict[str, Any] | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(ChannelFeedbackEventORM)
                .filter(
                    ChannelFeedbackEventORM.id == feedback_id,
                    ChannelFeedbackEventORM.tenant_id == tenant_id,
                )
                .first()
            )
            if row is None:
                return None
            row.triage_status = str(triage_status or "new").strip() or "new"
            row.triage_owner = str(triage_owner or "").strip() or None
            row.triage_note = str(triage_note or "").strip() or None
            row.triaged_by = triaged_by
            row.triaged_at = _utcnow()
            db.commit()
            db.refresh(row)
            return {
                "id": row.id,
                "triage_status": row.triage_status,
                "triage_owner": row.triage_owner,
                "triage_note": row.triage_note,
                "triaged_at": row.triaged_at,
            }

    def analytics_summary(self, *, tenant_id: int, days: int = 14) -> dict[str, Any]:
        from_date = _utcnow() - timedelta(days=max(1, int(days)))
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            total_requests = (
                db.query(func.count(ChannelUsageEventORM.id))
                .filter(
                    ChannelUsageEventORM.tenant_id == tenant_id,
                    ChannelUsageEventORM.created_at >= from_date,
                )
                .scalar()
                or 0
            )
            avg_total_ms = (
                db.query(func.avg(ChannelUsageEventORM.total_ms))
                .filter(
                    ChannelUsageEventORM.tenant_id == tenant_id,
                    ChannelUsageEventORM.created_at >= from_date,
                    ChannelUsageEventORM.status == "ok",
                )
                .scalar()
                or 0
            )
            helpful = (
                db.query(func.count(ChannelFeedbackEventORM.id))
                .filter(
                    ChannelFeedbackEventORM.tenant_id == tenant_id,
                    ChannelFeedbackEventORM.created_at >= from_date,
                    ChannelFeedbackEventORM.helpful.is_(True),
                )
                .scalar()
                or 0
            )
            not_helpful = (
                db.query(func.count(ChannelFeedbackEventORM.id))
                .filter(
                    ChannelFeedbackEventORM.tenant_id == tenant_id,
                    ChannelFeedbackEventORM.created_at >= from_date,
                    ChannelFeedbackEventORM.helpful.is_(False),
                )
                .scalar()
                or 0
            )
        return {
            "total_requests": int(total_requests),
            "avg_total_ms": round(float(avg_total_ms or 0.0), 2),
            "feedback_helpful": int(helpful),
            "feedback_not_helpful": int(not_helpful),
            "from_date": from_date.isoformat(),
        }

    def analytics_events(self, *, tenant_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            rows = (
                db.query(ChannelUsageEventORM)
                .filter(ChannelUsageEventORM.tenant_id == tenant_id)
                .order_by(desc(ChannelUsageEventORM.created_at))
                .limit(max(1, min(int(limit), 500)))
                .all()
            )
        return [
            {
                "id": row.id,
                "credential_id": row.credential_id,
                "channel_type": row.channel_type,
                "status": row.status,
                "question": row.question,
                "kb_uuid": row.kb_uuid,
                "query_run_id": row.query_run_id,
                "response_ms": int(row.response_ms or 0),
                "llm_ms": int(row.llm_ms or 0),
                "context_build_ms": int(row.context_build_ms or 0),
                "total_ms": int(row.total_ms or 0),
                "origin": row.origin,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    def analytics_feedback(self, *, tenant_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            rows = (
                db.query(ChannelFeedbackEventORM)
                .filter(ChannelFeedbackEventORM.tenant_id == tenant_id)
                .order_by(desc(ChannelFeedbackEventORM.created_at))
                .limit(max(1, min(int(limit), 500)))
                .all()
            )
        return [
            {
                "id": row.id,
                "credential_id": row.credential_id,
                "channel_type": row.channel_type,
                "query_run_id": row.query_run_id,
                "trace_id": row.trace_id,
                "helpful": row.helpful,
                "reason": row.reason,
                "note": row.note,
                "triage_status": row.triage_status,
                "triage_owner": row.triage_owner,
                "triage_note": row.triage_note,
                "triaged_at": row.triaged_at.isoformat() if row.triaged_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


class ChannelAccessService:
    def __init__(self, repository: ChannelAccessRepository):
        self._repo = repository

    def ensure_storage(self) -> None:
        self._repo.ensure_storage()

    def authenticate(self, *, tenant_id: int, secret: str, origin: str | None) -> ChannelPrincipal | None:
        return self._repo.authenticate(tenant_id=tenant_id, presented_secret=secret, origin=origin)

    def can_consume_question(self, principal: ChannelPrincipal) -> tuple[bool, str]:
        usage = self._repo.current_usage(tenant_id=principal.tenant_id, credential_id=principal.credential_id)
        if usage["daily"] >= max(1, int(principal.daily_limit)):
            return False, "Napi kérdéslimit elérve."
        if usage["minute"] >= max(1, int(principal.per_minute_limit)):
            return False, "Túl sok kérés rövid idő alatt."
        return True, ""

    def reserve_question_slot(self, principal: ChannelPrincipal) -> tuple[bool, str, dict[str, Any] | None]:
        return self._repo.reserve_usage_slot(
            tenant_id=principal.tenant_id,
            credential_id=principal.credential_id,
            daily_limit=principal.daily_limit,
            per_minute_limit=principal.per_minute_limit,
        )

    def reserve_question_slot_with_session(
        self,
        principal: ChannelPrincipal,
        *,
        session_key: str | None,
        session_per_minute_limit: int,
        session_burst_10s_limit: int,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        return self._repo.reserve_usage_slot(
            tenant_id=principal.tenant_id,
            credential_id=principal.credential_id,
            daily_limit=principal.daily_limit,
            per_minute_limit=principal.per_minute_limit,
            session_key=session_key,
            session_per_minute_limit=session_per_minute_limit,
            session_burst_10s_limit=session_burst_10s_limit,
        )

    def release_question_slot(self, reservation: dict[str, Any] | None) -> None:
        self._repo.release_usage_slot(reservation)

    def __getattr__(self, name: str):
        return getattr(self._repo, name)

