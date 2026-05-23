# backend/apps/chat/channel_access.py
# Feladat: Channel credential, origin-ellenőrzés, kvóta, usage, feedback és analytics repository/service logikát tartalmaz. A credential policy és quota reservation rész külön modulokba került, itt az adat-hozzáférési és orchestration felület marad. Program-specifikus channel access réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, func, text

from apps.chat.errors import ChannelCredentialPolicyInvalid
from apps.chat.channel_policy import (
    hash_channel_secret,
    normalize_ip_ranges,
    normalize_list,
    normalize_widget_origin,
    normalize_widget_origins,
    origin_value,
    remote_ip_allowed,
    verify_channel_signature,
)
from apps.chat.channel_quota import (
    release_usage_slot as release_channel_usage_slot,
    reserve_usage_slot as reserve_channel_usage_slot,
)
from apps.chat.channel_models import (
    ChannelCredentialORM,
    ChannelFeedbackEventORM,
    ChannelUsageEventORM,
)


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
    allowed_ip_ranges: list[str]
    require_signed_requests: bool
    presented_secret: str
    secret_version: str = "active"
    expires_at: datetime | None = None


class ChannelAccessRepository:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]) -> None:
        self._sf = session_factory
        self._quota_lock = threading.RLock()
        self._quota_fallback_counters: dict[str, int] = {}

    @staticmethod
    def _normalize_list(values: list[str] | None) -> list[str]:
        return normalize_list(values)

    @classmethod
    def _normalize_widget_origin(cls, value: str) -> str:
        return normalize_widget_origin(value)

    @classmethod
    def _normalize_widget_origins(cls, values: list[str] | None) -> list[str]:
        return normalize_widget_origins(values)

    @staticmethod
    def _hash_secret(secret: str) -> str:
        return hash_channel_secret(secret)

    @staticmethod
    def _origin_value(origin: str | None) -> str:
        return origin_value(origin)

    @staticmethod
    def _normalize_ip_ranges(values: list[str] | None) -> list[str]:
        return normalize_ip_ranges(values)

    @staticmethod
    def _active_secret_hash(row: ChannelCredentialORM) -> str:
        return str(getattr(row, "active_secret_hash", "") or getattr(row, "secret_hash", "") or "")

    @classmethod
    def _promote_next_secret_if_due(cls, row: ChannelCredentialORM, *, now: datetime) -> bool:
        rotating_until = getattr(row, "rotating_until", None)
        next_prefix = str(getattr(row, "next_key_prefix", "") or "").strip().lower()
        next_hash = str(getattr(row, "next_secret_hash", "") or "")
        if not rotating_until or rotating_until > now:
            return False
        if not next_prefix or not next_hash:
            row.next_key_prefix = None
            row.next_secret_hash = None
            row.rotating_until = None
            row.secret_version = "active"
            return True
        row.key_prefix = next_prefix
        row.active_secret_hash = next_hash
        row.secret_hash = next_hash
        row.next_key_prefix = None
        row.next_secret_hash = None
        row.rotating_until = None
        row.secret_version = "active"
        return True

    @staticmethod
    def _resolve_secret_version(
        *,
        prefix: str,
        incoming_hash: str,
        active_prefix: str,
        active_hash: str,
        next_prefix: str,
        next_hash: str,
        rotating_until: datetime | None,
        now: datetime,
    ) -> str | None:
        active_matches = bool(active_hash) and prefix == active_prefix and secrets.compare_digest(active_hash, incoming_hash)
        next_matches = (
            bool(next_hash)
            and prefix == next_prefix
            and rotating_until is not None
            and rotating_until >= now
            and secrets.compare_digest(next_hash, incoming_hash)
        )
        if active_matches:
            return "active"
        if next_matches:
            return "next"
        return None

    def ensure_storage(self) -> None:
        # Runtime repositoryk nem végezhetnek DDL-t. A public channel táblák és indexek
        # a core.modules.tenant.schema.public migrációs/bootstrap lépésben jönnek létre.
        return None

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
        allowed_ip_ranges: list[str] | None = None,
        require_signed_requests: bool = False,
        expires_at: datetime | None = None,
        created_by: int | None = None,
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
            raise ChannelCredentialPolicyInvalid("Widget credential esetén az allowed_origins megadása kötelező.")
        normalized_allowed_ip_ranges = self._normalize_ip_ranges(allowed_ip_ranges)
        require_signature = bool(require_signed_requests)
        if normalized_channel_type == "api" and not normalized_allowed_ip_ranges and not require_signature:
            raise ChannelCredentialPolicyInvalid("API credential esetén allowed_ip_ranges vagy require_signed_requests kötelező.")
        row = ChannelCredentialORM(
            tenant_id=tenant_id,
            channel_type=normalized_channel_type,
            name=str(name or "Unnamed").strip() or "Unnamed",
            key_prefix=prefix,
            active_secret_hash=self._hash_secret(secret_value),
            secret_hash=self._hash_secret(secret_value),
            secret_version="active",
            status="active",
            allowed_kb_uuids=self._normalize_list(allowed_kb_uuids),
            daily_limit=max(1, int(daily_limit)),
            per_minute_limit=max(1, int(per_minute_limit)),
            allowed_origins=normalized_allowed_origins,
            allowed_ip_ranges=normalized_allowed_ip_ranges,
            require_signed_requests=require_signature,
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
            "active_secret": secret_value,
            "status": row.status,
            "secret_version": str(getattr(row, "secret_version", "active") or "active"),
            "allowed_kb_uuids": list(row.allowed_kb_uuids or []),
            "daily_limit": int(row.daily_limit or 0),
            "per_minute_limit": int(row.per_minute_limit or 0),
            "allowed_origins": list(row.allowed_origins or []),
            "allowed_ip_ranges": list(row.allowed_ip_ranges or []),
            "require_signed_requests": bool(row.require_signed_requests),
            "can_use_signed_request": bool(row.require_signed_requests),
            "rate_limit_policy": {
                "daily_limit": int(row.daily_limit or 0),
                "per_minute_limit": int(row.per_minute_limit or 0),
            },
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
                    "secret_version": str(getattr(row, "secret_version", "active") or "active"),
                    "allowed_kb_uuids": list(row.allowed_kb_uuids or []),
                    "daily_limit": int(row.daily_limit or 0),
                    "per_minute_limit": int(row.per_minute_limit or 0),
                    "allowed_origins": list(row.allowed_origins or []),
                    "allowed_ip_ranges": list(row.allowed_ip_ranges or []),
                    "require_signed_requests": bool(row.require_signed_requests),
                    "can_use_signed_request": bool(row.require_signed_requests),
                    "rotating_until": row.rotating_until,
                    "rate_limit_policy": {
                        "daily_limit": int(row.daily_limit or 0),
                        "per_minute_limit": int(row.per_minute_limit or 0),
                    },
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
        allowed_ip_ranges: list[str] | None = None,
        require_signed_requests: bool | None = None,
        updated_by: int | None = None,
        expires_at: datetime | None = None,
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
                        raise ChannelCredentialPolicyInvalid("Widget credential esetén az allowed_origins nem lehet üres.")
                    row.allowed_origins = normalized_allowed_origins
                else:
                    row.allowed_origins = self._normalize_list(allowed_origins)
            if allowed_ip_ranges is not None:
                row.allowed_ip_ranges = self._normalize_ip_ranges(allowed_ip_ranges)
            if require_signed_requests is not None:
                row.require_signed_requests = bool(require_signed_requests)
            if str(row.channel_type or "widget").strip().lower() == "api":
                if not list(row.allowed_ip_ranges or []) and not bool(row.require_signed_requests):
                    raise ChannelCredentialPolicyInvalid("API credential esetén allowed_ip_ranges vagy require_signed_requests kötelező.")
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
                "allowed_ip_ranges": list(row.allowed_ip_ranges or []),
                "require_signed_requests": bool(row.require_signed_requests),
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
        rotating_until = _utcnow() + timedelta(days=7)
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
            row.next_key_prefix = prefix
            row.next_secret_hash = self._hash_secret(secret_value)
            row.rotating_until = rotating_until
            row.secret_version = "rotating"
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
                "next_key_prefix": row.next_key_prefix,
                "next_secret": secret_value,
                "secret_version": str(getattr(row, "secret_version", "rotating") or "rotating"),
                "rotating_until": row.rotating_until,
                "updated_at": row.updated_at,
            }

    def authenticate_with_reason(
        self,
        *,
        tenant_id: int,
        presented_secret: str,
        origin: str | None,
    ) -> tuple[ChannelPrincipal | None, str]:
        presented_secret = str(presented_secret or "").strip()
        if not presented_secret or "." not in presented_secret:
            return None, "invalid_credential"
        prefix = presented_secret.split(".", 1)[0].strip().lower()
        if not prefix:
            return None, "invalid_credential"
        now = _utcnow()
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(ChannelCredentialORM)
                .filter(
                    ChannelCredentialORM.tenant_id == tenant_id,
                    (
                        (ChannelCredentialORM.key_prefix == prefix)
                        | (ChannelCredentialORM.next_key_prefix == prefix)
                    ),
                )
                .first()
            )
            if row is None:
                return None, "invalid_credential"
            status = str(row.status or "").strip().lower()
            if status == "revoked":
                return None, "credential_revoked"
            if status != "active":
                return None, "invalid_credential"
            if row.expires_at is not None and row.expires_at <= now:
                return None, "credential_expired"
            promoted = self._promote_next_secret_if_due(row, now=now)
            expected_hash = self._active_secret_hash(row)
            incoming_hash = self._hash_secret(presented_secret)
            active_prefix = str(row.key_prefix or "").strip().lower()
            next_prefix = str(getattr(row, "next_key_prefix", "") or "").strip().lower()
            next_hash = str(getattr(row, "next_secret_hash", "") or "")
            rotating_until = getattr(row, "rotating_until", None)
            secret_version = self._resolve_secret_version(
                prefix=prefix,
                incoming_hash=incoming_hash,
                active_prefix=active_prefix,
                active_hash=expected_hash,
                next_prefix=next_prefix,
                next_hash=next_hash,
                rotating_until=rotating_until,
                now=now,
            )
            if not secret_version:
                return None, "invalid_credential"
            allowed_origins = [str(item).lower() for item in (row.allowed_origins or []) if str(item or "").strip()]
            if row.channel_type == "widget":
                if not allowed_origins:
                    return None, "invalid_origin"
                origin_value = self._origin_value(origin)
                if not origin_value or origin_value not in allowed_origins:
                    return None, "invalid_origin"
            row.last_used_at = now
            row.secret_version = secret_version
            if promoted:
                row.updated_at = now
            db.commit()
            return (
                ChannelPrincipal(
                    tenant_id=tenant_id,
                    credential_id=int(row.id),
                    channel_type=str(row.channel_type or "widget"),
                    allowed_kb_uuids=[str(item) for item in (row.allowed_kb_uuids or []) if str(item or "").strip()],
                    daily_limit=max(1, int(row.daily_limit or 1)),
                    per_minute_limit=max(1, int(row.per_minute_limit or 1)),
                    allowed_origins=list(row.allowed_origins or []),
                    allowed_ip_ranges=list(row.allowed_ip_ranges or []),
                    require_signed_requests=bool(row.require_signed_requests),
                    presented_secret=presented_secret,
                    secret_version=secret_version,
                    expires_at=row.expires_at,
                ),
                "",
            )

    def authenticate(
        self,
        *,
        tenant_id: int,
        presented_secret: str,
        origin: str | None,
    ) -> ChannelPrincipal | None:
        principal, _ = self.authenticate_with_reason(
            tenant_id=tenant_id,
            presented_secret=presented_secret,
            origin=origin,
        )
        return principal

    def authorize_api_request(
        self,
        principal: ChannelPrincipal,
        *,
        remote_ip: str | None,
        method: str,
        path: str,
        body: bytes,
        timestamp: str | None,
        nonce: str | None,
        signature: str | None,
        body_hash: str | None = None,
    ) -> tuple[bool, str]:
        if str(principal.channel_type or "widget").strip().lower() != "api":
            return True, ""
        ip_ranges = [str(item) for item in (principal.allowed_ip_ranges or []) if str(item or "").strip()]
        signature_required = bool(principal.require_signed_requests)
        ip_allowed = remote_ip_allowed(remote_ip, ip_ranges) if ip_ranges else False
        if ip_ranges and not ip_allowed:
            return False, "missing_ip_allowlist: Channel API credential IP allowlist rejected this request."
        if signature_required:
            return verify_channel_signature(
                secret=principal.presented_secret,
                method=method,
                path=path,
                body=body,
                timestamp=timestamp,
                nonce=nonce,
                signature=signature,
                body_hash=body_hash,
                credential_id=principal.credential_id,
            )
        if not ip_ranges:
            return False, "missing_ip_allowlist: Channel API credential requires IP allowlist or signed requests."
        return True, ""

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
        return reserve_channel_usage_slot(
            tenant_id=tenant_id,
            credential_id=credential_id,
            daily_limit=daily_limit,
            per_minute_limit=per_minute_limit,
            now=now,
            period_key=day_key,
            quota_lock=self._quota_lock,
            quota_fallback_counters=self._quota_fallback_counters,
            session_key=session_key,
            session_per_minute_limit=session_per_minute_limit,
            session_burst_10s_limit=session_burst_10s_limit,
        )

    def release_usage_slot(self, reservation: dict[str, Any] | None) -> None:
        release_channel_usage_slot(
            reservation,
            quota_lock=self._quota_lock,
            quota_fallback_counters=self._quota_fallback_counters,
        )

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

    def authenticate_with_reason(
        self,
        *,
        tenant_id: int,
        secret: str,
        origin: str | None,
    ) -> tuple[ChannelPrincipal | None, str]:
        return self._repo.authenticate_with_reason(
            tenant_id=tenant_id,
            presented_secret=secret,
            origin=origin,
        )

    def authorize_api_request(
        self,
        principal: ChannelPrincipal,
        *,
        remote_ip: str | None,
        method: str,
        path: str,
        body: bytes,
        timestamp: str | None,
        nonce: str | None,
        signature: str | None,
        body_hash: str | None = None,
    ) -> tuple[bool, str]:
        return self._repo.authorize_api_request(
            principal,
            remote_ip=remote_ip,
            method=method,
            path=path,
            body=body,
            timestamp=timestamp,
            nonce=nonce,
            signature=signature,
            body_hash=body_hash,
        )

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

