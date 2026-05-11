from __future__ import annotations

import logging
import hashlib
import json
from datetime import date, datetime, timedelta

from sqlalchemy import func, text

from core.capabilities.auth.dto.session import Session
from core.extensions.tenant.models.tenant_orm import TenantORM
from core.kernel.config import app_settings
from core.kernel.clock import utc_now
from core.kernel.db.model_bases import PublicBase
from core.kernel.logging.observability import get_metrics_snapshot
from core.platform_admin.models import (
    PlatformAdminMfaAttemptORM,
    PlatformSecurityAlertORM,
    PlatformAdminInviteTokenORM,
    PlatformAdminRefreshTokenORM,
    PlatformAdminUserORM,
    PlatformSecurityIpBanORM,
)
from core.platform_admin.event_catalog import ALL_MONITORING_EVENTS, EVENT_CATEGORIES
from core.platform_admin.schema_migrations import apply_platform_security_alerts_legacy_compat

logger = logging.getLogger(__name__)


class PlatformAdminRepository:
    def __init__(self, session_factory):
        self._sf = session_factory

    def ensure_security_storage(self) -> None:
        PublicBase.metadata.create_all(
            bind=self._sf.engine,
            tables=[
                PlatformSecurityIpBanORM.__table__,
                PlatformSecurityAlertORM.__table__,
                PlatformAdminMfaAttemptORM.__table__,
            ],
        )
        # Runtime guard: deploy-time migration should already handle this, but
        # keep startup resilient on older databases.
        apply_platform_security_alerts_legacy_compat(self._sf.engine)

    @staticmethod
    def _is_datetime_future(value: datetime | None, *, now: datetime) -> bool:
        if value is None:
            return False
        if value.tzinfo is None and now.tzinfo is None:
            return value > now
        if value.tzinfo is None and now.tzinfo is not None:
            return value.replace(tzinfo=now.tzinfo) > now
        if value.tzinfo is not None and now.tzinfo is None:
            return value > now.replace(tzinfo=value.tzinfo)
        return value > now

    @staticmethod
    def _is_datetime_gte(value: datetime | None, *, threshold: datetime) -> bool:
        if value is None:
            return False
        if value.tzinfo is None and threshold.tzinfo is None:
            return value >= threshold
        if value.tzinfo is None and threshold.tzinfo is not None:
            return value.replace(tzinfo=threshold.tzinfo) >= threshold
        if value.tzinfo is not None and threshold.tzinfo is None:
            return value >= threshold.replace(tzinfo=value.tzinfo)
        return value >= threshold

    @staticmethod
    def _metrics_summary() -> dict:
        snapshot = get_metrics_snapshot()
        req_count = snapshot.get("platform.request.count", {})
        req_latency = snapshot.get("platform.request.latency.ms", {})
        req_2xx = snapshot.get("platform.request.status.2xx.count", {})
        req_4xx = snapshot.get("platform.request.status.4xx.count", {})
        req_5xx = snapshot.get("platform.request.status.5xx.count", {})
        req_errors = snapshot.get("platform.request.error.count", {})
        req_unhandled = snapshot.get("platform.request.unhandled_error.count", {})
        rate_limit_hits = snapshot.get("platform.rate_limit.hit.count", {})
        auth_failure = snapshot.get("platform.auth.failure.count", {})
        permission_denied = snapshot.get("platform.auth.permission_denied.count", {})
        db_query_latency = snapshot.get("platform.db.query.ms", {})
        db_error = snapshot.get("platform.db.error.count", {})
        outbox_failed = snapshot.get("platform.outbox.failed.count", {})
        latency_count = float(req_latency.get("count") or 0.0)
        latency_sum = float(req_latency.get("sum") or 0.0)
        avg_latency_ms = round(latency_sum / latency_count, 2) if latency_count > 0 else 0.0
        return {
            "request_count": int(req_count.get("sum") or 0),
            "request_error_count": int(req_errors.get("sum") or 0),
            "request_2xx_count": int(req_2xx.get("sum") or 0),
            "request_4xx_count": int(req_4xx.get("sum") or 0),
            "request_5xx_count": int(req_5xx.get("sum") or 0),
            "unhandled_error_count": int(req_unhandled.get("sum") or 0),
            "rate_limit_hit_count": int(rate_limit_hits.get("sum") or 0),
            "auth_failure_count": int(auth_failure.get("sum") or 0),
            "permission_denied_count": int(permission_denied.get("sum") or 0),
            "db_error_count": int(db_error.get("sum") or 0),
            "outbox_failed_count": int(outbox_failed.get("sum") or 0),
            "request_latency_avg_ms": avg_latency_ms,
            "request_latency_max_ms": round(float(req_latency.get("max") or 0.0), 2),
            "request_latency_last_ms": round(float(req_latency.get("last") or 0.0), 2),
            "db_latency_avg_ms": round(float(db_query_latency.get("sum") or 0.0) / max(float(db_query_latency.get("count") or 0.0), 1.0), 2)
            if float(db_query_latency.get("count") or 0.0) > 0
            else 0.0,
            "db_latency_max_ms": round(float(db_query_latency.get("max") or 0.0), 2),
        }

    def _upsert_security_alerts(self, db, attack_signals: list[dict], now: datetime) -> list[dict]:
        alerts: list[dict] = []
        for signal in attack_signals:
            signal_name = str(signal.get("signal") or "").strip()
            severity = str(signal.get("severity") or "medium").strip().lower()
            category = "security"
            value = int(signal.get("value") or 0)
            alert_key = f"{category}:{severity}:{signal_name}"
            row = db.query(PlatformSecurityAlertORM).filter(PlatformSecurityAlertORM.alert_key == alert_key).first()
            if row is None:
                row = PlatformSecurityAlertORM(
                    alert_key=alert_key,
                    category=category,
                    severity=severity,
                    signal=signal_name,
                    title=signal_name,
                    value=value,
                    hit_count=1,
                    status="open",
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(row)
                db.flush()
            else:
                row.value = value
                row.hit_count = int(row.hit_count or 0) + 1
                row.last_seen_at = now
                row.status = "open"
                row.acknowledged_at = None
                row.acknowledged_by = None
            alerts.append(
                {
                    "id": int(row.id or 0),
                    "key": row.alert_key,
                    "category": row.category,
                    "severity": row.severity,
                    "title": row.title,
                    "signal": row.signal,
                    "value": int(row.value or 0),
                    "hit_count": int(row.hit_count or 0),
                    "status": row.status,
                    "first_seen_at": row.first_seen_at,
                    "last_seen_at": row.last_seen_at,
                    "acknowledged_at": row.acknowledged_at,
                    "acknowledged_by": row.acknowledged_by,
                }
            )
        db.commit()
        return alerts

    def list_users(self) -> list[PlatformAdminUserORM]:
        with self._sf() as db:
            return (
                db.query(PlatformAdminUserORM)
                .order_by(PlatformAdminUserORM.created_at.desc(), PlatformAdminUserORM.id.desc())
                .all()
            )

    def get_by_id(self, user_id: int) -> PlatformAdminUserORM | None:
        with self._sf() as db:
            return db.query(PlatformAdminUserORM).filter(PlatformAdminUserORM.id == user_id).first()

    def get_by_email(self, email: str) -> PlatformAdminUserORM | None:
        normalized = email.strip().lower()
        with self._sf() as db:
            return db.query(PlatformAdminUserORM).filter(func.lower(PlatformAdminUserORM.email) == normalized).first()

    def create_user(
        self,
        *,
        email: str,
        name: str | None,
        password_hash: str,
        is_active: bool,
        registration_completed_at: datetime | None,
        created_by: int | None = None,
    ) -> PlatformAdminUserORM:
        with self._sf() as db:
            row = PlatformAdminUserORM(
                email=email.strip().lower(),
                name=(name or "").strip() or None,
                password_hash=password_hash,
                is_active=is_active,
                role="admin",
                registration_completed_at=registration_completed_at,
                created_by=created_by,
                updated_by=created_by,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def update_user(
        self,
        user_id: int,
        *,
        email: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
        password_hash: str | None = None,
        registration_completed_at: datetime | None = None,
        failed_login_attempts: int | None = None,
        mfa_enabled: bool | None = None,
        mfa_secret_base32: str | None = None,
        mfa_pending_secret_base32: str | None = None,
        mfa_pending_expires_at: datetime | None = None,
        mfa_recovery_codes_hashes: str | None = None,
        bump_security_version: bool = False,
        updated_by: int | None = None,
    ) -> PlatformAdminUserORM | None:
        with self._sf() as db:
            row = db.query(PlatformAdminUserORM).filter(PlatformAdminUserORM.id == user_id).first()
            if not row:
                return None
            if email is not None:
                row.email = email.strip().lower()
            if name is not None:
                row.name = name.strip() or None
            if is_active is not None:
                row.is_active = is_active
            if password_hash is not None:
                row.password_hash = password_hash
            if registration_completed_at is not None:
                row.registration_completed_at = registration_completed_at
            if failed_login_attempts is not None:
                row.failed_login_attempts = failed_login_attempts
            if mfa_enabled is not None:
                row.mfa_enabled = mfa_enabled
            if mfa_secret_base32 is not None:
                row.mfa_secret_base32 = mfa_secret_base32
            if mfa_pending_secret_base32 is not None:
                row.mfa_pending_secret_base32 = mfa_pending_secret_base32
            if mfa_pending_expires_at is not None:
                row.mfa_pending_expires_at = mfa_pending_expires_at
            if mfa_recovery_codes_hashes is not None:
                row.mfa_recovery_codes_hashes = mfa_recovery_codes_hashes
            if bump_security_version:
                row.security_version = int(row.security_version or 0) + 1
            row.updated_by = updated_by
            db.commit()
            db.refresh(row)
            return row

    def upsert_pending_mfa_secret(
        self,
        user_id: int,
        *,
        pending_secret_base32: str,
        pending_expires_at: datetime,
        updated_by: int | None = None,
    ) -> PlatformAdminUserORM | None:
        with self._sf() as db:
            row = db.query(PlatformAdminUserORM).filter(PlatformAdminUserORM.id == user_id).first()
            if row is None:
                return None
            row.mfa_pending_secret_base32 = pending_secret_base32
            row.mfa_pending_expires_at = pending_expires_at
            row.updated_by = updated_by
            db.commit()
            db.refresh(row)
            return row

    def enable_mfa(
        self,
        user_id: int,
        *,
        secret_base32: str,
        recovery_code_hashes: list[str],
        updated_by: int | None = None,
    ) -> PlatformAdminUserORM | None:
        with self._sf() as db:
            row = db.query(PlatformAdminUserORM).filter(PlatformAdminUserORM.id == user_id).first()
            if row is None:
                return None
            row.mfa_enabled = True
            row.mfa_secret_base32 = secret_base32
            row.mfa_pending_secret_base32 = None
            row.mfa_pending_expires_at = None
            row.mfa_recovery_codes_hashes = json.dumps([str(v) for v in recovery_code_hashes if str(v).strip()])
            row.security_version = int(row.security_version or 0) + 1
            row.updated_by = updated_by
            db.commit()
            db.refresh(row)
            return row

    def disable_mfa(self, user_id: int, *, updated_by: int | None = None) -> PlatformAdminUserORM | None:
        with self._sf() as db:
            row = db.query(PlatformAdminUserORM).filter(PlatformAdminUserORM.id == user_id).first()
            if row is None:
                return None
            row.mfa_enabled = False
            row.mfa_secret_base32 = None
            row.mfa_pending_secret_base32 = None
            row.mfa_pending_expires_at = None
            row.mfa_recovery_codes_hashes = "[]"
            row.security_version = int(row.security_version or 0) + 1
            row.updated_by = updated_by
            db.commit()
            db.refresh(row)
            return row

    def consume_mfa_recovery_code(self, user_id: int, *, code_hash: str, updated_by: int | None = None) -> bool:
        with self._sf() as db:
            row = db.query(PlatformAdminUserORM).filter(PlatformAdminUserORM.id == user_id).first()
            if row is None:
                return False
            raw = str(row.mfa_recovery_codes_hashes or "[]")
            try:
                hashes = [str(v) for v in json.loads(raw) if str(v).strip()]
            except Exception:
                hashes = []
            if code_hash not in hashes:
                return False
            hashes = [h for h in hashes if h != code_hash]
            row.mfa_recovery_codes_hashes = json.dumps(hashes)
            row.updated_by = updated_by
            db.commit()
            return True

    def delete_user(self, user_id: int, *, deleted_by: int | None = None) -> bool:
        with self._sf() as db:
            row = db.query(PlatformAdminUserORM).filter(PlatformAdminUserORM.id == user_id).first()
            if not row:
                return False
            row.is_active = False
            row.deleted_at = utc_now()
            row.deleted_by = deleted_by
            row.updated_by = deleted_by
            row.security_version = int(row.security_version or 0) + 1
            db.commit()
            return True

    def create_invite_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        created_by: int | None = None,
    ) -> None:
        with self._sf() as db:
            db.query(PlatformAdminInviteTokenORM).filter(
                PlatformAdminInviteTokenORM.user_id == user_id,
                PlatformAdminInviteTokenORM.used_at.is_(None),
            ).update({"used_at": utc_now(), "updated_by": created_by}, synchronize_session=False)
            db.add(
                PlatformAdminInviteTokenORM(
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    created_by=created_by,
                    updated_by=created_by,
                )
            )
            db.commit()

    def get_invite_token(self, token_hash: str) -> PlatformAdminInviteTokenORM | None:
        with self._sf() as db:
            return (
                db.query(PlatformAdminInviteTokenORM)
                .filter(PlatformAdminInviteTokenORM.token_hash == token_hash)
                .first()
            )

    def mark_invite_used(self, token_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            row = db.query(PlatformAdminInviteTokenORM).filter(PlatformAdminInviteTokenORM.id == token_id).first()
            if row:
                row.used_at = utc_now()
                row.updated_by = updated_by
                db.commit()

    def create_refresh_session(self, session: Session, *, created_by: int | None = None) -> Session:
        with self._sf() as db:
            row = PlatformAdminRefreshTokenORM(
                user_id=session.user_id,
                jti=session.jti,
                token_hash=session.token_hash,
                ip=session.ip,
                user_agent=session.user_agent,
                valid=session.valid,
                expires_at=session.expires_at,
                created_by=created_by if created_by is not None else session.user_id,
                updated_by=created_by if created_by is not None else session.user_id,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return session.persisted(id=row.id, created_at=row.created_at)

    def get_refresh_session_by_jti(self, jti: str) -> Session | None:
        with self._sf() as db:
            row = db.query(PlatformAdminRefreshTokenORM).filter(PlatformAdminRefreshTokenORM.jti == jti).first()
            if not row:
                return None
            return Session(
                id=row.id,
                user_id=row.user_id,
                jti=row.jti,
                token_hash=row.token_hash,
                valid=row.valid,
                ip=row.ip,
                user_agent=row.user_agent,
                expires_at=row.expires_at,
                created_at=row.created_at,
            )

    def update_refresh_session(self, session: Session, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            db.query(PlatformAdminRefreshTokenORM).filter(PlatformAdminRefreshTokenORM.id == session.id).update(
                {
                    "valid": session.valid,
                    "expires_at": session.expires_at,
                    "ip": session.ip,
                    "user_agent": session.user_agent,
                    "updated_by": updated_by if updated_by is not None else session.user_id,
                },
                synchronize_session=False,
            )
            db.commit()

    def invalidate_all_refresh_sessions_for_user(self, user_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            db.query(PlatformAdminRefreshTokenORM).filter(
                PlatformAdminRefreshTokenORM.user_id == user_id,
                PlatformAdminRefreshTokenORM.valid.is_(True),
            ).update({"valid": False, "updated_by": updated_by if updated_by is not None else user_id}, synchronize_session=False)
            db.commit()

    def is_platform_admin_mfa_scope_blocked(self, *, scope: str, scope_key: str) -> bool:
        normalized_scope = str(scope or "").strip()
        normalized_key = str(scope_key or "").strip()
        if not normalized_scope or not normalized_key:
            return False
        now = utc_now()
        with self._sf() as db:
            row = (
                db.query(PlatformAdminMfaAttemptORM)
                .filter(
                    PlatformAdminMfaAttemptORM.scope == normalized_scope,
                    PlatformAdminMfaAttemptORM.scope_key == normalized_key,
                )
                .first()
            )
            return bool(row and self._is_datetime_future(row.blocked_until, now=now))

    def record_platform_admin_mfa_failed_attempt(
        self,
        *,
        scope: str,
        scope_key: str,
        max_attempts: int,
        window_minutes: int,
        lock_minutes: int,
        actor_user_id: int | None = None,
    ) -> bool:
        normalized_scope = str(scope or "").strip()
        normalized_key = str(scope_key or "").strip()
        if not normalized_scope or not normalized_key:
            return False
        safe_max_attempts = max(1, int(max_attempts or 1))
        safe_window_minutes = max(1, int(window_minutes or 1))
        safe_lock_minutes = max(1, int(lock_minutes or 1))
        now = utc_now()
        with self._sf() as db:
            row = (
                db.query(PlatformAdminMfaAttemptORM)
                .filter(
                    PlatformAdminMfaAttemptORM.scope == normalized_scope,
                    PlatformAdminMfaAttemptORM.scope_key == normalized_key,
                )
                .first()
            )
            if row is None:
                row = PlatformAdminMfaAttemptORM(
                    scope=normalized_scope,
                    scope_key=normalized_key,
                    attempts=0,
                    window_started_at=now,
                    created_by=actor_user_id,
                    updated_by=actor_user_id,
                )
                db.add(row)
                db.flush()
            if self._is_datetime_future(row.blocked_until, now=now):
                row.updated_by = actor_user_id
                db.commit()
                return True
            if not self._is_datetime_gte(
                now,
                threshold=(row.window_started_at or now) + timedelta(minutes=safe_window_minutes),
            ):
                row.attempts = int(row.attempts or 0) + 1
            else:
                row.attempts = 1
                row.window_started_at = now
            blocked_now = int(row.attempts or 0) >= safe_max_attempts
            row.blocked_until = now + timedelta(minutes=safe_lock_minutes) if blocked_now else None
            row.updated_by = actor_user_id
            db.commit()
            return blocked_now

    def reset_platform_admin_mfa_attempts(
        self,
        *,
        scopes: list[tuple[str, str]],
        actor_user_id: int | None = None,
    ) -> None:
        normalized_scopes = [
            (str(scope or "").strip(), str(scope_key or "").strip())
            for scope, scope_key in (scopes or [])
            if str(scope or "").strip() and str(scope_key or "").strip()
        ]
        if not normalized_scopes:
            return
        now = utc_now()
        with self._sf() as db:
            for scope, scope_key in normalized_scopes:
                row = (
                    db.query(PlatformAdminMfaAttemptORM)
                    .filter(
                        PlatformAdminMfaAttemptORM.scope == scope,
                        PlatformAdminMfaAttemptORM.scope_key == scope_key,
                    )
                    .first()
                )
                if row is None:
                    continue
                row.attempts = 0
                row.window_started_at = now
                row.blocked_until = None
                row.updated_by = actor_user_id
            db.commit()

    def list_active_tenants(self) -> list[TenantORM]:
        with self._sf() as db:
            return (
                db.query(TenantORM)
                .filter(TenantORM.is_active.is_(True))
                .order_by(TenantORM.name.asc(), TenantORM.slug.asc())
                .all()
            )

    def list_tenants(self) -> list[TenantORM]:
        with self._sf() as db:
            return db.query(TenantORM).order_by(TenantORM.name.asc(), TenantORM.slug.asc()).all()

    @staticmethod
    def _quote_ident(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    @staticmethod
    def _table_exists(db, qualified_name: str) -> bool:
        return db.execute(text("SELECT to_regclass(:name)"), {"name": qualified_name}).scalar() is not None

    def _public_billing_metrics(self, db, tenant_id: int) -> dict:
        subscription = None
        if self._table_exists(db, "public.billing_subscriptions"):
            subscription = db.execute(
                text(
                    """
                    SELECT plan_code, billing_period, status, trial_started_at, trial_ends_at,
                           extra_kb_count, extra_storage_gb, carryover_addon_questions, carryover_training_chars,
                           scheduled_plan_code, scheduled_billing_period, created_at, updated_at
                    FROM public.billing_subscriptions
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().first()
        question_count = 0
        if self._table_exists(db, "public.billing_question_usage"):
            question_count = int(
                db.execute(
                    text("SELECT COALESCE(SUM(question_count), 0) FROM public.billing_question_usage WHERE tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id},
                ).scalar()
                or 0
            )
        training = {"trained_chars": 0, "storage_bytes": 0}
        if self._table_exists(db, "public.billing_training_usage"):
            row = db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(trained_chars), 0) AS trained_chars,
                           COALESCE(SUM(storage_bytes), 0) AS storage_bytes
                    FROM public.billing_training_usage
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().first()
            training = {"trained_chars": int(row["trained_chars"] or 0), "storage_bytes": int(row["storage_bytes"] or 0)} if row else training
        return {
            "subscription": dict(subscription) if subscription else None,
            "question_count": question_count,
            **training,
        }

    def _plan_names(self, db) -> dict[str, str]:
        if not self._table_exists(db, "public.billing_catalog_entries"):
            return {}
        rows = db.execute(
            text(
                """
                SELECT code, name
                FROM public.billing_catalog_entries
                WHERE entry_type = 'plan'
                """
            )
        ).mappings().all()
        return {str(row["code"]): str(row["name"]) for row in rows}

    @staticmethod
    def _billing_period_discount_percent(billing_period: str | None) -> int:
        normalized = str(billing_period or "monthly").strip().lower()
        if normalized == "quarterly":
            return 7
        if normalized == "yearly":
            return 15
        return 0

    def _billing_revenue_metrics(self, db) -> dict[str, int]:
        paid_this_year_cents = 0
        expected_monthly_revenue_cents = 0
        if self._table_exists(db, "public.billing_invoices"):
            paid_this_year_cents = int(
                db.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(total_cents), 0)
                        FROM public.billing_invoices
                        WHERE status IN ('paid', 'simulated_paid', 'manual_paid')
                          AND issued_at >= date_trunc('year', CURRENT_DATE)
                        """
                    )
                ).scalar()
                or 0
            )
        if self._table_exists(db, "public.billing_subscriptions") and self._table_exists(db, "public.billing_catalog_entries"):
            rows = db.execute(
                text(
                    """
                    SELECT sub.plan_code, sub.billing_period, sub.extra_kb_count, sub.extra_storage_gb,
                           COALESCE(plan.price_cents, 0) AS price_cents
                    FROM public.billing_subscriptions sub
                    LEFT JOIN public.billing_catalog_entries plan
                      ON plan.entry_type = 'plan' AND plan.code = sub.plan_code
                    WHERE sub.plan_code <> 'free'
                      AND sub.status IN ('active', 'trial')
                    """
                )
            ).mappings().all()
            for row in rows:
                price_cents = int(row["price_cents"] or 0)
                discount = self._billing_period_discount_percent(row["billing_period"])
                discounted_monthly = round(price_cents * (100 - discount) / 100)
                recurring_addons_monthly = (int(row["extra_kb_count"] or 0) * 500) + (int(row["extra_storage_gb"] or 0) * 500)
                expected_monthly_revenue_cents += max(0, int(discounted_monthly) + recurring_addons_monthly)
        return {
            "paid_this_year_cents": paid_this_year_cents,
            "expected_annual_revenue_cents": expected_monthly_revenue_cents * 12,
            "expected_average_monthly_revenue_cents": expected_monthly_revenue_cents,
        }

    def _tenant_schema_metrics(self, db, slug: str) -> dict:
        schema = self._quote_ident(slug)

        def table_exists(table_name: str) -> bool:
            return self._table_exists(db, f"{schema}.{self._quote_ident(table_name)}")

        def scalar(sql: str, default: int = 0):
            try:
                return db.execute(text(sql)).scalar() or default
            except Exception:
                return default

        users = int(scalar(f"SELECT COUNT(*) FROM {schema}.users WHERE deleted_at IS NULL") if table_exists("users") else 0)
        knowledge_bases = int(
            scalar(f"SELECT COUNT(*) FROM {schema}.knowledge_bases WHERE deleted_at IS NULL") if table_exists("knowledge_bases") else 0
        )
        collection_names: set[str] = set()
        if table_exists("knowledge_bases"):
            kb_collections = db.execute(
                text(
                    f"""
                    SELECT qdrant_collection_name
                    FROM {schema}.knowledge_bases
                    WHERE deleted_at IS NULL
                    """
                )
            ).scalars().all()
            collection_names.update(str(name or "").strip() for name in kb_collections)
        if table_exists("knowledge_index_builds"):
            build_collections = db.execute(
                text(
                    f"""
                    SELECT collection_name
                    FROM {schema}.knowledge_index_builds
                    WHERE collection_name IS NOT NULL
                    """
                )
            ).scalars().all()
            collection_names.update(str(name or "").strip() for name in build_collections)
        collection_names.discard("")
        file_bytes = 0
        if table_exists("knowledge_ingest_inputs") and table_exists("knowledge_ingest_items"):
            file_bytes = int(
                scalar(
                    f"""
                    SELECT COALESCE(SUM(inputs.size_bytes), 0)
                    FROM {schema}.knowledge_ingest_inputs inputs
                    JOIN {schema}.knowledge_ingest_items items ON items.id = inputs.ingest_item_id
                    WHERE inputs.input_type = 'file'
                    """,
                )
            )
        database_bytes = int(
            db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(pg_total_relation_size(format('%I.%I', schemaname, tablename)::regclass)), 0)
                    FROM pg_tables
                    WHERE schemaname = :schema_name
                    """
                ),
                {"schema_name": slug},
            ).scalar()
            or 0
        )
        query_count = 0
        last_query_at = None
        avg_latency_ms = 0.0
        if table_exists("knowledge_query_runs"):
            query_row = db.execute(
                text(
                    f"""
                    SELECT COUNT(*) AS count, MAX(created_at) AS last_query_at, COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
                    FROM {schema}.knowledge_query_runs
                    """
                )
            ).mappings().first()
            if query_row:
                query_count = int(query_row["count"] or 0)
                last_query_at = query_row["last_query_at"]
                avg_latency_ms = round(float(query_row["avg_latency_ms"] or 0.0), 2)
        training_runs = 0
        training_items = 0
        training_completed = 0
        training_failed = 0
        last_training_at = None
        if table_exists("knowledge_ingest_runs"):
            training_row = db.execute(
                text(
                    f"""
                    SELECT COUNT(*) AS runs,
                           COALESCE(SUM(batch_size), 0) AS items,
                           COALESCE(SUM(completed_count), 0) AS completed,
                           COALESCE(SUM(failed_count), 0) AS failed,
                           MAX(COALESCE(completed_at, updated_at, created_at)) AS last_training_at
                    FROM {schema}.knowledge_ingest_runs
                    """
                )
            ).mappings().first()
            if training_row:
                training_runs = int(training_row["runs"] or 0)
                training_items = int(training_row["items"] or 0)
                training_completed = int(training_row["completed"] or 0)
                training_failed = int(training_row["failed"] or 0)
                last_training_at = training_row["last_training_at"]
        return {
            "users": users,
            "knowledge_bases": knowledge_bases,
            "query_count": query_count,
            "last_query_at": last_query_at,
            "avg_latency_ms": avg_latency_ms,
            "training_runs": training_runs,
            "training_items": training_items,
            "training_completed": training_completed,
            "training_failed": training_failed,
            "last_training_at": last_training_at,
            "file_bytes": max(0, file_bytes),
            "database_bytes": max(0, database_bytes),
            "qdrant_collection_names": sorted(collection_names),
        }

    @staticmethod
    def _build_qdrant_client():
        try:
            from qdrant_client import QdrantClient

            url = str(getattr(app_settings, "qdrant_url", "") or "").strip()
            if not url:
                return None
            kwargs = {"url": url, "check_compatibility": False}
            api_key = str(getattr(app_settings, "qdrant_api_key", "") or "").strip()
            if api_key:
                kwargs["api_key"] = api_key
            timeout = getattr(app_settings, "qdrant_timeout_sec", None)
            if timeout is not None:
                kwargs["timeout"] = int(timeout)
            return QdrantClient(**kwargs)
        except Exception:
            logger.debug("platform_admin.statistics.qdrant_client_failed", exc_info=True)
            return None

    @staticmethod
    def _qdrant_collection_stats(client, collection_names: list[str]) -> dict:
        qdrant_bytes = 0
        qdrant_points = 0
        qdrant_vectors = 0
        if client is None:
            return {"qdrant_bytes": 0, "qdrant_points": 0, "qdrant_vectors": 0}
        for collection_name in collection_names:
            try:
                info = client.get_collection(collection_name=collection_name)
                points_count = int(getattr(info, "points_count", None) or 0)
                vectors_count = int(getattr(info, "vectors_count", None) or points_count or 0)
                vector_size = 3072
                try:
                    vectors_config = getattr(getattr(info, "config", None), "params", None)
                    vectors = getattr(vectors_config, "vectors", None)
                    if getattr(vectors, "size", None):
                        vector_size = int(vectors.size)
                except Exception:
                    vector_size = 3072
                qdrant_bytes += max(0, vectors_count * vector_size * 4)
                qdrant_points += max(0, points_count)
                qdrant_vectors += max(0, vectors_count)
            except Exception:
                logger.debug("platform_admin.statistics.qdrant_collection_failed", exc_info=True)
        return {
            "qdrant_bytes": qdrant_bytes,
            "qdrant_points": qdrant_points,
            "qdrant_vectors": qdrant_vectors,
        }

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month = value.month - 1 + months
        year = value.year + month // 12
        month = month % 12 + 1
        day = min(value.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return date(year, month, day)

    @classmethod
    def _last_12_month_keys(cls) -> list[str]:
        current_month = date.today().replace(day=1)
        start = cls._add_months(current_month, -11)
        return [cls._add_months(start, idx).strftime("%Y-%m") for idx in range(12)]

    @classmethod
    def _period_bounds(cls, subscription: dict, tenant_created_at: datetime | None) -> dict:
        end_raw = subscription.get("trial_ends_at")
        period = str(subscription.get("billing_period") or "monthly").lower()
        months = 12 if period == "yearly" else 3 if period == "quarterly" else 1
        if isinstance(end_raw, datetime):
            end_date = end_raw.date()
        else:
            end_date = date.today().replace(day=1)
            end_date = cls._add_months(end_date, 1) - timedelta(days=1)
        start_date = cls._add_months(end_date + timedelta(days=1), -months)
        created_date = tenant_created_at.date() if isinstance(tenant_created_at, datetime) else None
        if created_date is not None and created_date > start_date:
            start_date = created_date
        return {
            "start_iso": start_date.isoformat(),
            "end_iso": end_date.isoformat(),
        }

    def platform_tenant_statistics_detail(self, tenant_id: int) -> dict | None:
        month_keys = self._last_12_month_keys()
        month_start = f"{month_keys[0]}-01"
        with self._sf() as db:
            plan_names = self._plan_names(db)
            tenant = db.query(TenantORM).filter(TenantORM.id == int(tenant_id)).first()
            if tenant is None:
                return None
            domains = db.execute(
                text(
                    """
                    SELECT domain, verified_at, created_at
                    FROM public.tenant_domains
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC, domain ASC
                    """
                ),
                {"tenant_id": int(tenant_id)},
            ).mappings().all()
            config = db.execute(
                text("SELECT package, feature_flags, limits FROM public.tenant_configs WHERE tenant_id = :tenant_id"),
                {"tenant_id": int(tenant_id)},
            ).mappings().first()
            billing = self._public_billing_metrics(db, int(tenant_id))
            subscription = billing["subscription"] or {}
            schema_metrics = self._tenant_schema_metrics(db, tenant.slug)
            qdrant_client = self._build_qdrant_client()
            qdrant_metrics = self._qdrant_collection_stats(qdrant_client, schema_metrics["qdrant_collection_names"])
            invoice_row = {"paid_total_cents": 0, "paid_invoice_count": 0}
            if self._table_exists(db, "public.billing_invoices"):
                paid = db.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(total_cents), 0) AS paid_total_cents,
                               COUNT(*) AS paid_invoice_count
                        FROM public.billing_invoices
                        WHERE tenant_id = :tenant_id
                          AND status IN ('simulated_paid', 'paid', 'manual_paid')
                        """
                    ),
                    {"tenant_id": int(tenant_id)},
                ).mappings().first()
                if paid:
                    invoice_row = {
                        "paid_total_cents": int(paid["paid_total_cents"] or 0),
                        "paid_invoice_count": int(paid["paid_invoice_count"] or 0),
                    }
            question_by_month = {key: 0 for key in month_keys}
            if self._table_exists(db, "public.billing_question_usage"):
                for row in db.execute(
                    text(
                        """
                        SELECT period_key, COALESCE(SUM(question_count), 0) AS questions
                        FROM public.billing_question_usage
                        WHERE tenant_id = :tenant_id AND period_key >= :start_key
                        GROUP BY period_key
                        """
                    ),
                    {"tenant_id": int(tenant_id), "start_key": month_keys[0]},
                ).mappings():
                    key = str(row["period_key"])
                    if key in question_by_month:
                        question_by_month[key] = int(row["questions"] or 0)
            training_by_month = {key: 0 for key in month_keys}
            if self._table_exists(db, "public.billing_training_usage"):
                for row in db.execute(
                    text(
                        """
                        SELECT period_key, COALESCE(SUM(trained_chars), 0) AS trained_chars
                        FROM public.billing_training_usage
                        WHERE tenant_id = :tenant_id AND period_key >= :start_key
                        GROUP BY period_key
                        """
                    ),
                    {"tenant_id": int(tenant_id), "start_key": month_keys[0]},
                ).mappings():
                    key = str(row["period_key"])
                    if key in training_by_month:
                        training_by_month[key] = int(row["trained_chars"] or 0)
            schema = self._quote_ident(tenant.slug)

            def tenant_table_exists(table_name: str) -> bool:
                return self._table_exists(db, f"{schema}.{self._quote_ident(table_name)}")

            usage_hours_by_month = {key: set() for key in month_keys}
            schema_questions_by_month = {key: 0 for key in month_keys}
            training_runs_by_month = {key: 0 for key in month_keys}
            if tenant_table_exists("knowledge_query_runs"):
                for row in db.execute(
                    text(
                        f"""
                        SELECT to_char(created_at, 'YYYY-MM') AS month_key,
                               COUNT(*) AS questions,
                               array_agg(DISTINCT to_char(date_trunc('hour', created_at), 'YYYY-MM-DD HH24')) AS hour_keys
                        FROM {schema}.knowledge_query_runs
                        WHERE created_at >= :month_start
                        GROUP BY month_key
                        """
                    ),
                    {"month_start": month_start},
                ).mappings():
                    key = str(row["month_key"])
                    if key in schema_questions_by_month:
                        schema_questions_by_month[key] = int(row["questions"] or 0)
                        usage_hours_by_month[key].update(str(item) for item in (row["hour_keys"] or []) if item)
            if tenant_table_exists("knowledge_ingest_runs"):
                for row in db.execute(
                    text(
                        f"""
                        SELECT to_char(created_at, 'YYYY-MM') AS month_key,
                               COUNT(*) AS runs,
                               array_agg(DISTINCT to_char(date_trunc('hour', created_at), 'YYYY-MM-DD HH24')) AS hour_keys
                        FROM {schema}.knowledge_ingest_runs
                        WHERE created_at >= :month_start
                        GROUP BY month_key
                        """
                    ),
                    {"month_start": month_start},
                ).mappings():
                    key = str(row["month_key"])
                    if key in training_runs_by_month:
                        training_runs_by_month[key] = int(row["runs"] or 0)
                        usage_hours_by_month[key].update(str(item) for item in (row["hour_keys"] or []) if item)
            monthly = [
                {
                    "month": key,
                    "questions": int(question_by_month[key] or schema_questions_by_month[key] or 0),
                    "training_chars": int(training_by_month[key] or 0),
                    "training_runs": int(training_runs_by_month[key] or 0),
                    "usage_hours": len(usage_hours_by_month[key]),
                }
                for key in month_keys
            ]
            package_code = subscription.get("plan_code") or (config["package"] if config else "free")
            package_name = plan_names.get(str(package_code), str(package_code or "free"))
            file_bytes = int(schema_metrics["file_bytes"] or billing["storage_bytes"] or 0)
            database_bytes = int(schema_metrics["database_bytes"] or 0)
            qdrant_bytes = int(qdrant_metrics["qdrant_bytes"] or 0)
            return {
                "tenant": {
                    "id": int(tenant.id),
                    "slug": tenant.slug,
                    "name": tenant.name,
                    "is_active": bool(tenant.is_active),
                    "created_at": tenant.created_at,
                    "updated_at": tenant.updated_at,
                },
                "billing": {
                    "package_code": package_code,
                    "package_name": package_name,
                    "billing_period": subscription.get("billing_period"),
                    "status": subscription.get("status"),
                    "current_period": self._period_bounds(subscription, tenant.created_at),
                    **invoice_row,
                },
                "domains": [
                    {
                        "domain": row["domain"],
                        "verified": row["verified_at"] is not None,
                        "verified_at": row["verified_at"],
                        "created_at": row["created_at"],
                    }
                    for row in domains
                ],
                "feature_flags": dict(config["feature_flags"] or {}) if config else {},
                "limits": dict(config["limits"] or {}) if config else {},
                "usage": {
                    "questions": int(billing["question_count"] or schema_metrics["query_count"] or 0),
                    "trained_chars": int(billing["trained_chars"] or 0),
                    "storage_bytes": file_bytes + database_bytes + qdrant_bytes,
                    "file_bytes": file_bytes,
                    "database_bytes": database_bytes,
                    "qdrant_bytes": qdrant_bytes,
                    "qdrant_points": int(qdrant_metrics["qdrant_points"] or 0),
                    "qdrant_vectors": int(qdrant_metrics["qdrant_vectors"] or 0),
                    "users": int(schema_metrics["users"] or 0),
                    "knowledge_bases": int(schema_metrics["knowledge_bases"] or 0),
                    "training_runs": int(schema_metrics["training_runs"] or 0),
                    "training_items": int(schema_metrics["training_items"] or 0),
                    "last_query_at": schema_metrics["last_query_at"],
                    "last_training_at": schema_metrics["last_training_at"],
                },
                "monthly": monthly,
            }

    def platform_statistics(self) -> dict:
        tenants = self.list_tenants()
        rows = []
        with self._sf() as db:
            plan_names = self._plan_names(db)
            qdrant_client = self._build_qdrant_client()
            for tenant in tenants:
                tenant_id = int(tenant.id)
                domains = db.execute(
                    text(
                        """
                        SELECT domain, verified_at, created_at
                        FROM public.tenant_domains
                        WHERE tenant_id = :tenant_id
                        ORDER BY created_at DESC, domain ASC
                        """
                    ),
                    {"tenant_id": tenant_id},
                ).mappings().all()
                config = db.execute(
                    text("SELECT package, feature_flags, limits FROM public.tenant_configs WHERE tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id},
                ).mappings().first()
                billing = self._public_billing_metrics(db, tenant_id)
                schema_metrics = self._tenant_schema_metrics(db, tenant.slug)
                qdrant_metrics = self._qdrant_collection_stats(qdrant_client, schema_metrics["qdrant_collection_names"])
                subscription = billing["subscription"] or {}
                package_code = subscription.get("plan_code") or (config["package"] if config else "free")
                package_name = plan_names.get(str(package_code), str(package_code or "free"))
                file_bytes = int(schema_metrics["file_bytes"] or billing["storage_bytes"] or 0)
                database_bytes = int(schema_metrics["database_bytes"] or 0)
                qdrant_bytes = int(qdrant_metrics["qdrant_bytes"] or 0)
                rows.append(
                    {
                        "id": tenant_id,
                        "slug": tenant.slug,
                        "name": tenant.name,
                        "is_active": bool(tenant.is_active),
                        "created_at": tenant.created_at,
                        "package_code": package_code,
                        "package_name": package_name,
                        "billing_period": subscription.get("billing_period"),
                        "subscription_status": subscription.get("status"),
                        "domains": [
                            {
                                "domain": row["domain"],
                                "verified": row["verified_at"] is not None,
                                "verified_at": row["verified_at"],
                                "created_at": row["created_at"],
                            }
                            for row in domains
                        ],
                        "domain_count": len(domains),
                        "verified_domain_count": sum(1 for row in domains if row["verified_at"] is not None),
                        "feature_flags": dict(config["feature_flags"] or {}) if config else {},
                        "limits": dict(config["limits"] or {}) if config else {},
                        "usage": {
                            "questions": int(billing["question_count"] or schema_metrics["query_count"] or 0),
                            "schema_queries": int(schema_metrics["query_count"] or 0),
                            "trained_chars": int(billing["trained_chars"] or 0),
                            "storage_bytes": file_bytes + database_bytes + qdrant_bytes,
                            "file_bytes": file_bytes,
                            "database_bytes": database_bytes,
                            "qdrant_bytes": qdrant_bytes,
                            "qdrant_points": int(qdrant_metrics["qdrant_points"] or 0),
                            "qdrant_vectors": int(qdrant_metrics["qdrant_vectors"] or 0),
                            "users": int(schema_metrics["users"] or 0),
                            "knowledge_bases": int(schema_metrics["knowledge_bases"] or 0),
                            "training_runs": int(schema_metrics["training_runs"] or 0),
                            "training_items": int(schema_metrics["training_items"] or 0),
                            "training_completed": int(schema_metrics["training_completed"] or 0),
                            "training_failed": int(schema_metrics["training_failed"] or 0),
                            "avg_latency_ms": float(schema_metrics["avg_latency_ms"] or 0.0),
                            "last_query_at": schema_metrics["last_query_at"],
                            "last_training_at": schema_metrics["last_training_at"],
                        },
                    }
                )
        totals = {
            "tenants": len(rows),
            "active_tenants": sum(1 for row in rows if row["is_active"]),
            "questions": sum(int(row["usage"]["questions"] or 0) for row in rows),
            "schema_queries": sum(int(row["usage"]["schema_queries"] or 0) for row in rows),
            "trained_chars": sum(int(row["usage"]["trained_chars"] or 0) for row in rows),
            "storage_bytes": sum(int(row["usage"]["storage_bytes"] or 0) for row in rows),
            "file_bytes": sum(int(row["usage"]["file_bytes"] or 0) for row in rows),
            "database_bytes": sum(int(row["usage"]["database_bytes"] or 0) for row in rows),
            "qdrant_bytes": sum(int(row["usage"]["qdrant_bytes"] or 0) for row in rows),
            "qdrant_points": sum(int(row["usage"]["qdrant_points"] or 0) for row in rows),
            "qdrant_vectors": sum(int(row["usage"]["qdrant_vectors"] or 0) for row in rows),
            "users": sum(int(row["usage"]["users"] or 0) for row in rows),
            "knowledge_bases": sum(int(row["usage"]["knowledge_bases"] or 0) for row in rows),
            "training_runs": sum(int(row["usage"]["training_runs"] or 0) for row in rows),
            "training_items": sum(int(row["usage"]["training_items"] or 0) for row in rows),
            "domains": sum(int(row["domain_count"] or 0) for row in rows),
            "verified_domains": sum(int(row["verified_domain_count"] or 0) for row in rows),
            **self._billing_revenue_metrics(db),
        }
        return {"summary": totals, "tenants": rows}

    @staticmethod
    def _hash_ip(value: str | None) -> str:
        raw = (value or "").strip()
        if not raw:
            return "ismeretlen"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _details_to_dict(value) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    @classmethod
    def _canonical_events_from_audit_row(cls, row: dict) -> list[str]:
        action = str(row.get("action") or "").strip().lower()
        outcome = str(row.get("outcome") or "").strip().lower()
        details = cls._details_to_dict(row.get("details"))
        reason = str(details.get("reason") or "").strip().lower()
        events: list[str] = []

        if action in {"login_success", "platform_admin_login_success"}:
            events.append("login_success")
        if action in {"login_failed", "platform_admin_login_failed"}:
            events.append("login_failed")
        if action in {"logout", "platform_admin_logout"}:
            events.append("logout")
        if action == "forgot_password_link_sent":
            events.append("password_reset_requested")
        if action == "password_set_by_invite":
            events.append("password_reset_success")
        if action == "login_2fa_failed":
            events.append("mfa_failed")
        if action == "login_success" and bool(details.get("2fa")):
            events.append("mfa_success")
        if action in {"login_2fa_rate_limited"} or outcome == "rate_limited":
            events.append("rate_limit_triggered")
        if action in {"refresh_suspicious_fingerprint"}:
            events.append("suspicious_request")
        if action in {"platform_admin_security_ip_banned"}:
            events.append("blocked_ip")
        if action in {"refresh_failed", "logout_failed", "platform_admin_refresh_failed"} and reason in {"invalid_token", "wrong_type", "unknown_jti"}:
            events.append("invalid_token")
        if action in {"refresh_failed", "logout_failed"} and reason in {"expired_token", "session_expired"}:
            events.append("expired_token")
        if action in {"refresh_failed"} and reason in {"permissions_changed", "security_version_mismatch"}:
            events.append("permission_denied")
        if action in {"platform_admin_login_success"}:
            events.append("admin_login")
        if action.startswith("platform_admin_") and action not in {"platform_admin_login_success", "platform_admin_login_failed"}:
            events.append("admin_action")
        if action == "user_created":
            events.append("user_registered")
        if action == "tenant_provisioned":
            events.append("workspace_created")

        return list(dict.fromkeys(events))

    @staticmethod
    def _event_summary_rows(counters: dict[str, int]) -> list[dict]:
        rows: list[dict] = []
        for event_name in ALL_MONITORING_EVENTS:
            count = int(counters.get(event_name, 0))
            rows.append(
                {
                    "event": event_name,
                    "category": EVENT_CATEGORIES.get(event_name, "other"),
                    "count": count,
                    "status": "active" if count > 0 else "not_detected",
                }
            )
        return rows

    @staticmethod
    def _rule_row(
        *,
        rule_id: str,
        priority: str,
        title: str,
        wake_up: bool,
        status: str,
        value: float | int | None = None,
        threshold: float | int | None = None,
        window_minutes: int | None = None,
        reason: str | None = None,
    ) -> dict:
        return {
            "rule_id": rule_id,
            "priority": priority,
            "title": title,
            "wake_up": wake_up,
            "status": status,
            "value": value,
            "threshold": threshold,
            "window_minutes": window_minutes,
            "reason": reason,
        }

    def _build_alert_rule_results(
        self,
        *,
        now: datetime,
        risk_rows: list[dict],
        event_counters: dict[str, int],
        metrics_summary: dict,
    ) -> list[dict]:
        window_5m = now - timedelta(minutes=5)
        window_10m = now - timedelta(minutes=10)
        window_24h = now - timedelta(hours=24)
        window_30d = now - timedelta(days=30)
        ip_failed_5m: dict[str, int] = {}
        email_failed_10m: dict[str, int] = {}
        failed_login_10m = 0
        for row in risk_rows:
            action = str(row.get("action") or "").strip().lower()
            created_at = row.get("created_at")
            details = self._details_to_dict(row.get("details"))
            if action not in {"login_failed", "platform_admin_login_failed"}:
                continue
            if isinstance(created_at, datetime) and self._is_datetime_gte(created_at, threshold=window_10m):
                failed_login_10m += 1
                email = str(details.get("email") or "").strip().lower()
                if email:
                    email_failed_10m[email] = int(email_failed_10m.get(email, 0)) + 1
            if isinstance(created_at, datetime) and self._is_datetime_gte(created_at, threshold=window_5m):
                ip = str(row.get("ip") or "").strip()
                if ip:
                    ip_failed_5m[ip] = int(ip_failed_5m.get(ip, 0)) + 1

        admin_new_ip_count = 0
        admin_new_ip_check_available = True
        try:
            with self._sf() as db:
                if self._table_exists(db, "public.audit_log"):
                    current_ip_rows = db.execute(
                        text(
                            """
                            SELECT DISTINCT ip
                            FROM public.audit_log
                            WHERE created_at >= :window_24h
                              AND action = 'platform_admin_login_success'
                              AND ip IS NOT NULL
                              AND ip <> ''
                            """
                        ),
                        {"window_24h": window_24h},
                    ).scalars().all()
                    baseline_ips = set(
                        db.execute(
                            text(
                                """
                                SELECT DISTINCT ip
                                FROM public.audit_log
                                WHERE created_at >= :window_30d
                                  AND created_at < :window_24h
                                  AND action = 'platform_admin_login_success'
                                  AND ip IS NOT NULL
                                  AND ip <> ''
                                """
                            ),
                            {"window_30d": window_30d, "window_24h": window_24h},
                        ).scalars().all()
                    )
                    admin_new_ip_count = sum(1 for ip in current_ip_rows if ip not in baseline_ips)
        except Exception:
            admin_new_ip_count = 0
            admin_new_ip_check_available = False

        max_failed_ip_5m = max(ip_failed_5m.values()) if ip_failed_5m else 0
        max_failed_email_10m = max(email_failed_10m.values()) if email_failed_10m else 0
        request_count = float(metrics_summary.get("request_count") or 0.0)
        request_error_count = float(metrics_summary.get("request_error_count") or 0.0)
        db_error_count = int(metrics_summary.get("db_error_count") or 0)
        error_rate_pct = (request_error_count / request_count * 100.0) if request_count > 0 else 0.0

        rows: list[dict] = []
        rows.append(
            self._rule_row(
                rule_id="p1_api_not_responding",
                priority="P1",
                title="API nem válaszol",
                wake_up=True,
                status="triggered" if request_count <= 0 else "ok",
                value=int(request_count),
                threshold=1,
                window_minutes=10,
                reason="MVP heurisztika: 0 request a figyelési ablakban",
            )
        )
        rows.append(
            self._rule_row(
                rule_id="p1_db_unreachable",
                priority="P1",
                title="DB nem elérhető",
                wake_up=True,
                status="triggered" if db_error_count > 0 else "ok",
                value=db_error_count,
                threshold=1,
                window_minutes=10,
                reason="MVP heurisztika: db_error esemény(ek) a figyelési ablakban",
            )
        )
        rows.append(
            self._rule_row(
                rule_id="p1_login_outage",
                priority="P1",
                title="Login teljesen leáll",
                wake_up=True,
                status="triggered" if failed_login_10m >= 20 and int(event_counters.get("login_success", 0)) == 0 else "ok",
                value=failed_login_10m,
                threshold=20,
                window_minutes=10,
            )
        )
        rows.append(self._rule_row(rule_id="p1_payment_outage", priority="P1", title="Fizetés teljesen leáll", wake_up=True, status="unavailable", reason="Payment watchdog nincs bekötve"))
        rows.append(self._rule_row(rule_id="p1_disk_usage_high", priority="P1", title="Disk usage > 90%", wake_up=True, status="unavailable", reason="Host/container disk metrika nincs bekötve"))
        rows.append(self._rule_row(rule_id="p1_restart_loop", priority="P1", title="Container/app folyamatos restart", wake_up=True, status="unavailable", reason="Container restart metrika nincs bekötve"))
        rows.append(self._rule_row(rule_id="p1_failed_login_same_ip", priority="P1", title="10 sikertelen login 5 percen belül ugyanarról az IP-ről", wake_up=True, status="triggered" if max_failed_ip_5m >= 10 else "ok", value=max_failed_ip_5m, threshold=10, window_minutes=5))
        rows.append(self._rule_row(rule_id="p1_failed_login_same_email", priority="P1", title="20 sikertelen login 10 percen belül ugyanarra az emailre", wake_up=True, status="triggered" if max_failed_email_10m >= 20 else "ok", value=max_failed_email_10m, threshold=20, window_minutes=10))
        rows.append(
            self._rule_row(
                rule_id="p1_admin_login_new_country_ip",
                priority="P1",
                title="Admin login új országból/IP-ről",
                wake_up=True,
                status="triggered" if admin_new_ip_count > 0 else "ok" if admin_new_ip_check_available else "unavailable",
                value=admin_new_ip_count if admin_new_ip_check_available else None,
                threshold=1 if admin_new_ip_check_available else None,
                window_minutes=24 * 60 if admin_new_ip_check_available else None,
                reason=(
                    "MVP: IP-alapú baseline összehasonlítás aktív (GeoIP nélkül)"
                    if admin_new_ip_check_available
                    else "GeoIP nincs bekötve, IP-alapú újdonság figyelés aktív lesz login event esetén"
                ),
            )
        )
        rows.append(self._rule_row(rule_id="p1_privilege_escalation", priority="P1", title="Privilege escalation attempt", wake_up=True, status="triggered" if int(event_counters.get("privilege_escalation_attempt", 0)) > 0 else "ok", value=int(event_counters.get("privilege_escalation_attempt", 0)), threshold=1, window_minutes=10))
        rows.append(self._rule_row(rule_id="p1_permission_denied_spike", priority="P1", title="Sok permission_denied rövid idő alatt", wake_up=True, status="triggered" if int(event_counters.get("permission_denied", 0)) >= 15 else "ok", value=int(event_counters.get("permission_denied", 0)), threshold=15, window_minutes=10))
        rows.append(self._rule_row(rule_id="p1_rate_limit_spike", priority="P1", title="Rate limit spike", wake_up=True, status="triggered" if int(metrics_summary.get("rate_limit_hit_count") or 0) >= 50 else "ok", value=int(metrics_summary.get("rate_limit_hit_count") or 0), threshold=50, window_minutes=10))
        rows.append(self._rule_row(rule_id="p1_token_abuse", priority="P1", title="Token abuse / sok invalid token", wake_up=True, status="triggered" if int(event_counters.get("invalid_token", 0)) >= 20 else "ok", value=int(event_counters.get("invalid_token", 0)), threshold=20, window_minutes=10))
        rows.append(self._rule_row(rule_id="p2_api_latency_p95", priority="P2", title="API p95 latency > 1 sec 10 percig", wake_up=False, status="unavailable", reason="P95 histogram metrika nincs bekötve"))
        rows.append(self._rule_row(rule_id="p2_error_rate", priority="P2", title="Error rate > 2%", wake_up=False, status="triggered" if request_count >= 100 and error_rate_pct > 2.0 else "ok", value=round(error_rate_pct, 2), threshold=2.0, window_minutes=10))
        rows.append(self._rule_row(rule_id="p2_db_slow_query_spike", priority="P2", title="DB slow query spike", wake_up=False, status="unavailable", reason="Slow query metrika nincs bekötve"))
        rows.append(self._rule_row(rule_id="p2_queue_failure_rise", priority="P2", title="Queue job failure emelkedés", wake_up=False, status="triggered" if int(metrics_summary.get("outbox_failed_count") or 0) >= 5 else "ok", value=int(metrics_summary.get("outbox_failed_count") or 0), threshold=5, window_minutes=10))
        rows.append(self._rule_row(rule_id="p2_payment_failed_rise", priority="P2", title="Sok payment failed, de nem teljes outage", wake_up=False, status="unavailable", reason="Payment failed metrika nincs bekötve"))
        rows.append(self._rule_row(rule_id="p2_new_device_login_rise", priority="P2", title="Sok új device login", wake_up=False, status="triggered" if int(event_counters.get("new_device_login", 0)) >= 10 else "ok", value=int(event_counters.get("new_device_login", 0)), threshold=10, window_minutes=60))
        rows.append(self._rule_row(rule_id="p3_deployment_finished", priority="P3", title="Deployment finished", wake_up=False, status="triggered" if int(event_counters.get("deployment_finished", 0)) > 0 else "ok", value=int(event_counters.get("deployment_finished", 0))))
        rows.append(self._rule_row(rule_id="p3_new_admin_created", priority="P3", title="Új admin user létrejött", wake_up=False, status="triggered" if int(event_counters.get("admin_action", 0)) > 0 else "ok", value=int(event_counters.get("admin_action", 0))))
        rows.append(self._rule_row(rule_id="p3_feature_flag_changed", priority="P3", title="Feature flag változás", wake_up=False, status="unavailable", reason="Feature flag audit esemény nincs bekötve"))
        rows.append(self._rule_row(rule_id="p3_usage_spike", priority="P3", title="Usage spike", wake_up=False, status="triggered" if request_count >= 1000 else "ok", value=int(request_count), threshold=1000, window_minutes=60))
        rows.append(self._rule_row(rule_id="p3_export_completed", priority="P3", title="Export completed", wake_up=False, status="triggered" if int(event_counters.get("export_completed", 0)) > 0 else "ok", value=int(event_counters.get("export_completed", 0))))
        return rows

    def _build_monitoring_metrics_catalog(
        self,
        *,
        risk_rows: list[dict],
        event_counters: dict[str, int],
        metrics_summary: dict,
        summary: dict,
    ) -> list[dict]:
        request_count = int(metrics_summary.get("request_count") or 0)
        request_error_count = int(metrics_summary.get("request_error_count") or 0)
        error_rate_pct = round((request_error_count / request_count * 100.0), 2) if request_count > 0 else 0.0
        failed_by_ip: dict[str, int] = {}
        failed_by_email: dict[str, int] = {}
        for row in risk_rows:
            action = str(row.get("action") or "").strip().lower()
            if action not in {"login_failed", "platform_admin_login_failed"}:
                continue
            ip = str(row.get("ip") or "").strip()
            if ip:
                failed_by_ip[ip] = int(failed_by_ip.get(ip, 0)) + 1
            details = self._details_to_dict(row.get("details"))
            email = str(details.get("email") or "").strip().lower()
            if email:
                failed_by_email[email] = int(failed_by_email.get(email, 0)) + 1
        top_failed_ip = sorted(failed_by_ip.items(), key=lambda x: x[1], reverse=True)[:5]
        top_failed_email = sorted(failed_by_email.items(), key=lambda x: x[1], reverse=True)[:5]

        def metric(
            *,
            domain: str,
            key: str,
            label: str,
            value=None,
            unit: str | None = None,
            status: str = "available",
            reason: str | None = None,
            details=None,
        ) -> dict:
            return {
                "domain": domain,
                "key": key,
                "label": label,
                "value": value,
                "unit": unit,
                "status": status,
                "reason": reason,
                "details": details,
            }

        rows: list[dict] = [
            metric(domain="application", key="request_count", label="request count", value=request_count, unit="count"),
            metric(domain="application", key="error_rate", label="error rate", value=error_rate_pct, unit="percent"),
            metric(domain="application", key="p95_response_time", label="p95 response time", status="unavailable", reason="P95 histogram metrika nincs bekötve"),
            metric(domain="application", key="p99_response_time", label="p99 response time", status="unavailable", reason="P99 histogram metrika nincs bekötve"),
            metric(domain="application", key="endpoint_latency", label="endpoint latency", status="unavailable", reason="Endpoint bontású latency metrika nincs bekötve"),
            metric(
                domain="application",
                key="status_code_breakdown",
                label="status code bontás 2xx/4xx/5xx",
                status="available",
                details=[
                    {"family": "2xx", "count": int(metrics_summary.get("request_2xx_count") or 0)},
                    {"family": "4xx", "count": int(metrics_summary.get("request_4xx_count") or 0)},
                    {"family": "5xx", "count": int(metrics_summary.get("request_5xx_count") or 0)},
                ],
            ),
            metric(domain="auth_security", key="failed_login_count", label="failed login count", value=int(summary.get("failed_login") or 0), unit="count"),
            metric(domain="auth_security", key="successful_login_count", label="successful login count", value=int(event_counters.get("login_success", 0)), unit="count"),
            metric(domain="auth_security", key="failed_login_per_ip", label="failed login per IP", value=max([count for _, count in top_failed_ip], default=0), unit="count", details=[{"ip": ip, "count": count} for ip, count in top_failed_ip]),
            metric(domain="auth_security", key="failed_login_per_email", label="failed login per email", value=max([count for _, count in top_failed_email], default=0), unit="count", details=[{"email": email, "count": count} for email, count in top_failed_email]),
            metric(domain="auth_security", key="admin_login_count", label="admin login count", value=int(event_counters.get("admin_login", 0)), unit="count"),
            metric(domain="auth_security", key="permission_denied_count", label="permission denied count", value=int(metrics_summary.get("permission_denied_count") or 0), unit="count"),
            metric(domain="auth_security", key="rate_limit_count", label="rate limit count", value=int(metrics_summary.get("rate_limit_hit_count") or 0), unit="count"),
            metric(domain="auth_security", key="invalid_token_count", label="invalid token count", value=int(event_counters.get("invalid_token", 0)), unit="count"),
            metric(domain="infrastructure", key="cpu_usage", label="CPU usage", status="unavailable", reason="Host/container CPU metrika nincs bekötve"),
            metric(domain="infrastructure", key="memory_usage", label="memory usage", status="unavailable", reason="Host/container memória metrika nincs bekötve"),
            metric(domain="infrastructure", key="disk_usage", label="disk usage", status="unavailable", reason="Host/container disk metrika nincs bekötve"),
            metric(domain="infrastructure", key="app_restart_count", label="app restart count", status="unavailable", reason="Container restart metrika nincs bekötve"),
            metric(domain="infrastructure", key="db_connection_count", label="DB connection count", status="unavailable", reason="DB connection pool metrika nincs bekötve"),
            metric(domain="infrastructure", key="db_latency", label="DB latency", value=float(metrics_summary.get("db_latency_avg_ms") or 0.0), unit="ms", status="available"),
            metric(domain="business", key="registration_count", label="registration count", value=int(event_counters.get("user_registered", 0)), unit="count"),
            metric(domain="business", key="active_users", label="active users", status="unavailable", reason="Aktív user aggregátum még nincs bekötve"),
            metric(domain="business", key="payment_success_rate", label="payment success rate", status="unavailable", reason="Payment success/failure event emitter nincs bekötve"),
            metric(domain="business", key="payment_failure_rate", label="payment failure rate", status="unavailable", reason="Payment success/failure event emitter nincs bekötve"),
            metric(domain="business", key="subscription_cancellation_count", label="subscription cancellation count", value=int(event_counters.get("subscription_cancelled", 0)), unit="count"),
        ]
        return rows

    @staticmethod
    def _metric_by_key(metrics: list[dict], key: str) -> dict | None:
        for metric in metrics:
            if str(metric.get("key") or "") == key:
                return metric
        return None

    def _build_dashboards(
        self,
        *,
        monitoring_metrics: list[dict],
        event_counters: dict[str, int],
        banned_ips: list[dict],
    ) -> list[dict]:
        failed_ip_metric = self._metric_by_key(monitoring_metrics, "failed_login_per_ip") or {}
        failed_email_metric = self._metric_by_key(monitoring_metrics, "failed_login_per_email") or {}
        login_success_metric = self._metric_by_key(monitoring_metrics, "successful_login_count") or {}
        login_failed_metric = self._metric_by_key(monitoring_metrics, "failed_login_count") or {}
        login_success = float(login_success_metric.get("value") or 0.0)
        login_failed = float(login_failed_metric.get("value") or 0.0)
        login_success_rate = round((login_success / max(login_success + login_failed, 1.0)) * 100.0, 2)
        active_blocked = sum(1 for row in banned_ips if bool(row.get("active")))
        return [
            {
                "id": "system_health",
                "title": "System health dashboard",
                "order": 1,
                "items": [
                    {"label": "uptime", "status": "unavailable", "reason": "Uptime forrás nincs bekötve"},
                    {"label": "API latency", "status": "available", "metric_key": "request_count"},
                    {"label": "error rate", "status": "available", "metric_key": "error_rate"},
                    {"label": "DB status", "status": "unavailable", "reason": "DB health probe nincs bekötve"},
                    {"label": "CPU / RAM / disk", "status": "unavailable", "reason": "Infra resource metrika nincs bekötve"},
                    {"label": "app restartok", "status": "unavailable", "reason": "Restart metrika nincs bekötve"},
                ],
            },
            {
                "id": "security",
                "title": "Security dashboard",
                "order": 2,
                "items": [
                    {"label": "failed login trend", "status": "available", "value": int(login_failed)},
                    {"label": "failed login IP szerint", "status": "available", "details": failed_ip_metric.get("details") or []},
                    {"label": "failed login email szerint", "status": "available", "details": failed_email_metric.get("details") or []},
                    {"label": "admin loginok", "status": "available", "value": int(event_counters.get("admin_login", 0))},
                    {"label": "permission denied", "status": "available", "value": int(event_counters.get("permission_denied", 0))},
                    {"label": "rate limit események", "status": "available", "metric_key": "rate_limit_count"},
                    {"label": "blocked IP-k", "status": "available", "value": active_blocked},
                    {"label": "suspicious requestek", "status": "available", "value": int(event_counters.get("suspicious_request", 0))},
                ],
            },
            {
                "id": "business_product",
                "title": "Business / product dashboard",
                "order": 3,
                "items": [
                    {"label": "regisztrációk", "status": "available", "metric_key": "registration_count"},
                    {"label": "login success rate", "status": "available", "value": login_success_rate, "unit": "percent"},
                    {"label": "payment success / failed", "status": "unavailable", "reason": "Payment success/failure event nincs bekötve"},
                    {"label": "aktív userek", "status": "unavailable", "reason": "Active users aggregátum nincs bekötve"},
                    {
                        "label": "subscription események",
                        "status": "available",
                        "value": int(event_counters.get("subscription_created", 0)) + int(event_counters.get("subscription_cancelled", 0)),
                    },
                ],
            },
        ]

    @staticmethod
    def _readiness_metric_available(monitoring_metrics: list[dict], key: str) -> bool:
        for metric in monitoring_metrics:
            if str(metric.get("key") or "") != key:
                continue
            return str(metric.get("status") or "") == "available"
        return False

    @staticmethod
    def _readiness_rule(alert_rule_results: list[dict], rule_id: str) -> dict | None:
        for row in alert_rule_results:
            if str(row.get("rule_id") or "") == rule_id:
                return row
        return None

    @staticmethod
    def _readiness_event_defined(event_stream_summary: list[dict], event_name: str) -> bool:
        for row in event_stream_summary:
            if str(row.get("event") or "") == event_name:
                return True
        return False

    def _build_mvp_readiness(
        self,
        *,
        monitoring_metrics: list[dict],
        alert_rule_results: list[dict],
        event_stream_summary: list[dict],
    ) -> dict:
        checks: list[dict] = []

        def add_check(
            *,
            check_id: str,
            label: str,
            configured: bool,
            runtime_status: str = "ok",
            detail: str | None = None,
        ) -> None:
            checks.append(
                {
                    "id": check_id,
                    "label": label,
                    "configured": configured,
                    "runtime_status": runtime_status,
                    "detail": detail,
                }
            )

        add_check(
            check_id="mvp_auth_event_logging",
            label="Auth log események",
            configured=self._readiness_event_defined(event_stream_summary, "login_success")
            and self._readiness_event_defined(event_stream_summary, "login_failed"),
            detail="login_success + login_failed eseménytaxonómia jelen van",
        )
        add_check(
            check_id="mvp_failed_login_per_ip",
            label="Failed login számlálás IP alapján",
            configured=self._readiness_metric_available(monitoring_metrics, "failed_login_per_ip"),
        )
        add_check(
            check_id="mvp_failed_login_per_email",
            label="Failed login számlálás email alapján",
            configured=self._readiness_metric_available(monitoring_metrics, "failed_login_per_email"),
        )
        add_check(
            check_id="mvp_rate_limit_logging",
            label="Rate limit log / metrika",
            configured=self._readiness_metric_available(monitoring_metrics, "rate_limit_count"),
        )
        add_check(
            check_id="mvp_permission_denied_logging",
            label="Permission denied log / metrika",
            configured=self._readiness_metric_available(monitoring_metrics, "permission_denied_count"),
        )
        add_check(
            check_id="mvp_admin_activity_logging",
            label="Admin login / admin action logging",
            configured=self._readiness_event_defined(event_stream_summary, "admin_login")
            and self._readiness_event_defined(event_stream_summary, "admin_action"),
        )
        add_check(
            check_id="mvp_api_error_rate_metric",
            label="API error rate metrika",
            configured=self._readiness_metric_available(monitoring_metrics, "error_rate"),
        )
        add_check(
            check_id="mvp_db_error_and_latency_metric",
            label="DB error / DB latency metrika",
            configured=self._readiness_metric_available(monitoring_metrics, "db_latency"),
        )

        p1_api_down = self._readiness_rule(alert_rule_results, "p1_api_not_responding")
        add_check(
            check_id="mvp_p1_api_down_alert",
            label="P1 alert: API down",
            configured=bool(p1_api_down) and str(p1_api_down.get("status") or "") != "unavailable",
            runtime_status="triggered" if bool(p1_api_down) and str(p1_api_down.get("status") or "") == "triggered" else "ok",
        )
        p1_db_down = self._readiness_rule(alert_rule_results, "p1_db_unreachable")
        add_check(
            check_id="mvp_p1_db_down_alert",
            label="P1 alert: DB down",
            configured=bool(p1_db_down) and str(p1_db_down.get("status") or "") != "unavailable",
            runtime_status="triggered" if bool(p1_db_down) and str(p1_db_down.get("status") or "") == "triggered" else "ok",
        )
        p1_bruteforce_ip = self._readiness_rule(alert_rule_results, "p1_failed_login_same_ip")
        p1_bruteforce_email = self._readiness_rule(alert_rule_results, "p1_failed_login_same_email")
        bruteforce_triggered = (
            (bool(p1_bruteforce_ip) and str(p1_bruteforce_ip.get("status") or "") == "triggered")
            or (bool(p1_bruteforce_email) and str(p1_bruteforce_email.get("status") or "") == "triggered")
        )
        add_check(
            check_id="mvp_p1_bruteforce_alert",
            label="P1 alert: bruteforce",
            configured=(
                bool(p1_bruteforce_ip)
                and str(p1_bruteforce_ip.get("status") or "") != "unavailable"
                and bool(p1_bruteforce_email)
                and str(p1_bruteforce_email.get("status") or "") != "unavailable"
            ),
            runtime_status="triggered" if bruteforce_triggered else "ok",
        )
        p1_admin_suspicious = self._readiness_rule(alert_rule_results, "p1_admin_login_new_country_ip")
        add_check(
            check_id="mvp_p1_admin_suspicious_alert",
            label="P1 alert: admin gyanús login",
            configured=bool(p1_admin_suspicious) and str(p1_admin_suspicious.get("status") or "") != "unavailable",
            runtime_status="triggered" if bool(p1_admin_suspicious) and str(p1_admin_suspicious.get("status") or "") == "triggered" else "ok",
            detail=str(p1_admin_suspicious.get("reason") or "") if bool(p1_admin_suspicious) else None,
        )

        total_checks = len(checks)
        configured_count = sum(1 for row in checks if bool(row.get("configured")))
        missing_count = total_checks - configured_count
        triggered_count = sum(1 for row in checks if str(row.get("runtime_status") or "") == "triggered")
        score_percent = int(round((configured_count / max(total_checks, 1)) * 100))

        if missing_count >= 3:
            overall_status = "red"
        elif missing_count > 0 or triggered_count > 0:
            overall_status = "yellow"
        else:
            overall_status = "green"

        return {
            "status": overall_status,
            "score_percent": score_percent,
            "configured_checks": configured_count,
            "total_checks": total_checks,
            "missing_checks": missing_count,
            "triggered_checks": triggered_count,
            "checks": checks,
        }

    def platform_security_monitoring(self) -> dict:
        # Runtime safety: ha a service bootstrap még nem futott (régi processz / részleges deploy),
        # monitoring kéréskor is biztosítjuk az alert/ip-ban tároló táblákat.
        self.ensure_security_storage()
        now = utc_now()
        window_24h = now - timedelta(hours=24)
        window_7d = now - timedelta(days=7)
        window_30d = now - timedelta(days=30)
        with self._sf() as db:
            event_counters: dict[str, int] = {name: 0 for name in ALL_MONITORING_EVENTS}
            risk_rows = []
            if self._table_exists(db, "public.audit_log"):
                risk_rows = db.execute(
                    text(
                        """
                        SELECT action,
                               outcome,
                               details,
                               ip,
                               created_at,
                               user_agent
                        FROM public.audit_log
                        WHERE created_at >= :window_24h
                          AND (
                            action IN (
                              'login_success',
                              'login_failed',
                              'logout',
                              'refresh_failed',
                              'logout_failed',
                              'logout_error',
                              'forgot_password_link_sent',
                              'password_set_by_invite',
                              'login_2fa_failed',
                              'login_2fa_rate_limited',
                              'platform_admin_login_success',
                              'platform_admin_login_failed',
                              'platform_admin_refresh_failed',
                              'platform_admin_logout',
                              'platform_admin_profile_updated',
                              'platform_admin_password_changed',
                              'platform_admin_stats_viewed',
                              'platform_admin_tenant_stats_viewed',
                              'platform_admin_security_ip_banned',
                              'platform_admin_security_ip_unbanned',
                              'platform_admin_security_alert_ack',
                              'user_created',
                              'tenant_provisioned'
                            )
                            OR action = 'refresh_suspicious_fingerprint'
                            OR outcome = 'rate_limited'
                          )
                        """
                    ),
                    {"window_24h": window_24h},
                ).mappings().all()

            failed_login = 0
            failed_refresh = 0
            failed_logout = 0
            suspicious_fingerprint = 0
            rate_limited = 0
            source_counter: dict[str, int] = {}
            events: list[dict] = []
            for row in risk_rows:
                for canonical_event in self._canonical_events_from_audit_row(row):
                    event_counters[canonical_event] = int(event_counters.get(canonical_event, 0)) + 1
                action = str(row.get("action") or "")
                outcome = str(row.get("outcome") or "")
                if action in {"login_failed", "platform_admin_login_failed"}:
                    failed_login += 1
                if action in {"refresh_failed", "platform_admin_refresh_failed"}:
                    failed_refresh += 1
                if action in {"logout_failed", "logout_error"}:
                    failed_logout += 1
                if action == "refresh_suspicious_fingerprint":
                    suspicious_fingerprint += 1
                if outcome == "rate_limited":
                    rate_limited += 1
                hashed = self._hash_ip(row.get("ip"))
                source_counter[hashed] = int(source_counter.get(hashed, 0)) + 1
                severity = "medium"
                if action in {"login_failed", "platform_admin_login_failed", "refresh_failed", "platform_admin_refresh_failed"}:
                    severity = "high"
                elif outcome == "rate_limited":
                    severity = "high"
                events.append(
                    {
                        "scope": "platform_admin",
                        "tenant": None,
                        "host": "platform-admin",
                        "action": action,
                        "outcome": outcome or None,
                        "ip": row.get("ip"),
                        "severity": severity,
                        "created_at": row.get("created_at"),
                        "possible_test_traffic": "pytest" in str(row.get("user_agent") or "").lower(),
                    }
                )

            top_sources = [
                {"source_hash": source_hash, "risk_events": count}
                for source_hash, count in sorted(source_counter.items(), key=lambda item: item[1], reverse=True)[:10]
            ]

            tenant_hotspots: list[dict] = []
            duplicate_users: dict[str, set[str]] = {}
            concurrent_ip_anomalies: list[dict] = []
            tenants = self.list_tenants()
            for tenant in tenants:
                schema = self._quote_ident(tenant.slug)
                tenant_audit_table = f"{schema}.audit_log"
                if self._table_exists(db, tenant_audit_table):
                    tenant_rows = db.execute(
                        text(
                            f"""
                            SELECT action, outcome, ip, created_at, user_agent
                            , details
                            FROM {tenant_audit_table}
                            WHERE created_at >= :window_24h
                              AND (
                                action IN (
                                  'login_success',
                                  'login_failed',
                                  'logout',
                                  'refresh_failed',
                                  'logout_failed',
                                  'logout_error',
                                  'forgot_password_link_sent',
                                  'password_set_by_invite',
                                  'login_2fa_failed',
                                  'login_2fa_rate_limited',
                                  'refresh_suspicious_fingerprint',
                                  'user_created',
                                  'tenant_provisioned'
                                )
                                OR outcome = 'rate_limited'
                              )
                            ORDER BY created_at DESC
                            LIMIT 100
                            """
                        ),
                        {"window_24h": window_24h},
                    ).mappings().all()
                    if tenant_rows:
                        tenant_hotspots.append(
                            {
                                "tenant": tenant.slug,
                                "host": f"{tenant.slug}.{getattr(app_settings, 'tenant_base_domain', 'host')}",
                                "risk_events": len(tenant_rows),
                            }
                        )
                    for row in tenant_rows:
                        for canonical_event in self._canonical_events_from_audit_row(row):
                            event_counters[canonical_event] = int(event_counters.get(canonical_event, 0)) + 1
                        action = str(row.get("action") or "")
                        outcome = str(row.get("outcome") or "")
                        severity = "medium"
                        if action in {"login_failed", "refresh_failed", "login_2fa_rate_limited"} or outcome == "rate_limited":
                            severity = "high"
                        events.append(
                            {
                                "scope": "tenant",
                                "tenant": tenant.slug,
                                "host": f"{tenant.slug}.{getattr(app_settings, 'tenant_base_domain', 'host')}",
                                "action": action,
                                "outcome": outcome or None,
                                "ip": row.get("ip"),
                                "severity": severity,
                                "created_at": row.get("created_at"),
                                "possible_test_traffic": "pytest" in str(row.get("user_agent") or "").lower(),
                            }
                        )

                users_table = f"{schema}.users"
                if self._table_exists(db, users_table):
                    for row in db.execute(
                        text(
                            f"""
                            SELECT lower(email) AS email
                            FROM {users_table}
                            WHERE deleted_at IS NULL
                              AND email IS NOT NULL
                            """
                        )
                    ).mappings():
                        email = str(row.get("email") or "").strip()
                        if not email:
                            continue
                        duplicate_users.setdefault(email, set()).add(tenant.slug)

                refresh_table = f"{schema}.refresh_tokens"
                if self._table_exists(db, refresh_table):
                    rows = db.execute(
                        text(
                            f"""
                            SELECT user_id, COUNT(DISTINCT ip) AS ip_count
                            FROM {refresh_table}
                            WHERE created_at >= :window_24h
                              AND ip IS NOT NULL
                              AND ip <> ''
                            GROUP BY user_id
                            HAVING COUNT(DISTINCT ip) >= 2
                            ORDER BY ip_count DESC
                            LIMIT 20
                            """
                        ),
                        {"window_24h": window_24h},
                    ).mappings().all()
                    for row in rows:
                        concurrent_ip_anomalies.append(
                            {
                                "tenant": tenant.slug,
                                "user_id": int(row["user_id"] or 0),
                                "distinct_ip_count_24h": int(row["ip_count"] or 0),
                            }
                        )

            new_tenants_24h = int(
                db.execute(
                    text("SELECT COUNT(*) FROM public.tenants WHERE created_at >= :window_24h"),
                    {"window_24h": window_24h},
                ).scalar()
                or 0
            )
            new_tenants_7d = int(
                db.execute(
                    text("SELECT COUNT(*) FROM public.tenants WHERE created_at >= :window_7d"),
                    {"window_7d": window_7d},
                ).scalar()
                or 0
            )
            new_tenants_30d = int(
                db.execute(
                    text("SELECT COUNT(*) FROM public.tenants WHERE created_at >= :window_30d"),
                    {"window_30d": window_30d},
                ).scalar()
                or 0
            )

            new_tenants_without_training_7d = 0
            if self._table_exists(db, "public.billing_training_usage"):
                new_tenants_without_training_7d = int(
                    db.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM public.tenants t
                            LEFT JOIN (
                                SELECT tenant_id, COALESCE(SUM(trained_chars), 0) AS trained_chars
                                FROM public.billing_training_usage
                                GROUP BY tenant_id
                            ) btu ON btu.tenant_id = t.id
                            WHERE t.created_at >= :window_7d
                              AND COALESCE(btu.trained_chars, 0) = 0
                            """
                        ),
                        {"window_7d": window_7d},
                    ).scalar()
                    or 0
                )

            risk_events_total = len(risk_rows)
            attack_signals: list[dict] = []
            if failed_login >= 10:
                attack_signals.append(
                    {"severity": "high", "signal": "Sok sikertelen belépés", "value": failed_login}
                )
            if failed_refresh >= 10:
                attack_signals.append(
                    {"severity": "high", "signal": "Sok sikertelen refresh token próbálkozás", "value": failed_refresh}
                )
            if rate_limited >= 20:
                attack_signals.append(
                    {"severity": "high", "signal": "Gyakori rate limit esemény", "value": rate_limited}
                )
            if suspicious_fingerprint > 0:
                attack_signals.append(
                    {"severity": "medium", "signal": "Gyanús refresh fingerprint eltérés", "value": suspicious_fingerprint}
                )
            if new_tenants_without_training_7d >= 5:
                attack_signals.append(
                    {"severity": "medium", "signal": "Sok új, de tanítás nélküli tenant", "value": new_tenants_without_training_7d}
                )

            if risk_events_total == 0 and new_tenants_without_training_7d < 3:
                ai_assessment = "Alacsony kockázat: az elmúlt 24 órában nem látszik kiugró auth/rate-limit támadási minta."
            elif risk_events_total >= 30 or rate_limited >= 20 or failed_login >= 15:
                ai_assessment = "Magas kockázat: célzott auth vagy rate-limit terhelés valószínű. Javasolt ideiglenes blokkolás és fokozott monitorozás."
            else:
                ai_assessment = "Közepes kockázat: vannak gyanús jelek, érdemes célzottan figyelni a forrásokat és a regisztrációs mintákat."

            duplicate_user_rows = [
                {"email": email, "tenants": sorted(list(slugs)), "tenant_count": len(slugs)}
                for email, slugs in duplicate_users.items()
                if len(slugs) >= 2
            ]
            duplicate_user_rows.sort(key=lambda item: item["tenant_count"], reverse=True)

            banned_ips = [
                {
                    "ip": row.ip,
                    "reason": row.reason,
                    "created_at": row.created_at,
                    "expires_at": row.expires_at,
                    "active": row.released_at is None
                    and (row.expires_at is None or self._is_datetime_future(row.expires_at, now=now)),
                }
                for row in self.list_ip_bans(limit=200)
            ]

            metrics_summary = self._metrics_summary()
            if int(metrics_summary.get("unhandled_error_count") or 0) > 0:
                event_counters["api_error"] = int(event_counters.get("api_error", 0)) + int(metrics_summary["unhandled_error_count"])
            if int(metrics_summary.get("outbox_failed_count") or 0) > 0:
                event_counters["queue_job_failed"] = int(event_counters.get("queue_job_failed", 0)) + int(metrics_summary["outbox_failed_count"])
                event_counters["background_job_failed"] = int(event_counters.get("background_job_failed", 0)) + int(metrics_summary["outbox_failed_count"])
            if int(metrics_summary.get("db_error_count") or 0) > 0:
                event_counters["db_error"] = int(event_counters.get("db_error", 0)) + int(metrics_summary["db_error_count"])
            alert_rule_results = self._build_alert_rule_results(
                now=now,
                risk_rows=risk_rows,
                event_counters=event_counters,
                metrics_summary=metrics_summary,
            )
            rule_trigger_signals = [
                {
                    "severity": "high" if row.get("priority") == "P1" else "medium" if row.get("priority") == "P2" else "low",
                    "signal": str(row.get("title") or ""),
                    "value": int(row.get("value") or 0),
                }
                for row in alert_rule_results
                if row.get("status") == "triggered"
            ]
            all_signals = attack_signals + rule_trigger_signals
            alerts = self._upsert_security_alerts(db, all_signals, now) if all_signals else self.list_security_alerts(limit=200)

            monitoring_metrics = self._build_monitoring_metrics_catalog(
                risk_rows=risk_rows,
                event_counters=event_counters,
                metrics_summary=metrics_summary,
                summary={
                    "failed_login": failed_login,
                },
            )
            event_stream_summary = self._event_summary_rows(event_counters)
            mvp_readiness = self._build_mvp_readiness(
                monitoring_metrics=monitoring_metrics,
                alert_rule_results=alert_rule_results,
                event_stream_summary=event_stream_summary,
            )
            return {
                "summary": {
                    "window_hours": 24,
                    "failed_login": failed_login,
                    "failed_refresh": failed_refresh,
                    "failed_logout": failed_logout,
                    "rate_limited": rate_limited,
                    "suspicious_fingerprint": suspicious_fingerprint,
                    "risk_events_total": risk_events_total,
                },
                "metrics_summary": metrics_summary,
                "events": sorted(events, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:200],
                "alerts": sorted(alerts, key=lambda item: str(item.get("last_seen_at") or ""), reverse=True)[:100],
                "tenant_hotspots": sorted(tenant_hotspots, key=lambda item: int(item["risk_events"]), reverse=True)[:30],
                "attack_signals": attack_signals,
                "top_sources": top_sources,
                "signup_watch": {
                    "new_tenants_24h": new_tenants_24h,
                    "new_tenants_7d": new_tenants_7d,
                    "new_tenants_30d": new_tenants_30d,
                    "new_tenants_without_training_7d": new_tenants_without_training_7d,
                },
                "duplicate_users": duplicate_user_rows[:100],
                "concurrent_ip_anomalies": sorted(
                    concurrent_ip_anomalies,
                    key=lambda item: int(item["distinct_ip_count_24h"]),
                    reverse=True,
                )[:100],
                "banned_ips": banned_ips,
                "ai_assessment": ai_assessment,
                "event_stream_summary": event_stream_summary,
                "alert_rule_results": alert_rule_results,
                "monitoring_metrics": monitoring_metrics,
                "mvp_readiness": mvp_readiness,
                "dashboards": self._build_dashboards(
                    monitoring_metrics=monitoring_metrics,
                    event_counters=event_counters,
                    banned_ips=banned_ips,
                ),
            }

    def list_security_alerts(self, *, limit: int = 200) -> list[dict]:
        self.ensure_security_storage()
        with self._sf() as db:
            rows = (
                db.query(PlatformSecurityAlertORM)
                .order_by(PlatformSecurityAlertORM.last_seen_at.desc(), PlatformSecurityAlertORM.id.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": int(row.id or 0),
                    "key": row.alert_key,
                    "category": row.category,
                    "severity": row.severity,
                    "title": row.title,
                    "signal": row.signal,
                    "value": int(row.value or 0),
                    "hit_count": int(row.hit_count or 0),
                    "status": row.status,
                    "first_seen_at": row.first_seen_at,
                    "last_seen_at": row.last_seen_at,
                    "acknowledged_at": row.acknowledged_at,
                    "acknowledged_by": row.acknowledged_by,
                }
                for row in rows
            ]

    def acknowledge_security_alert(self, alert_id: int, *, admin_user_id: int | None) -> dict | None:
        self.ensure_security_storage()
        with self._sf() as db:
            row = db.query(PlatformSecurityAlertORM).filter(PlatformSecurityAlertORM.id == int(alert_id)).first()
            if row is None:
                return None
            row.status = "acknowledged"
            row.acknowledged_at = utc_now()
            row.acknowledged_by = admin_user_id
            row.updated_by = admin_user_id
            db.commit()
            db.refresh(row)
            return {
                "id": int(row.id or 0),
                "status": row.status,
                "acknowledged_at": row.acknowledged_at,
                "acknowledged_by": row.acknowledged_by,
            }

    def is_ip_banned(self, ip: str | None) -> bool:
        normalized = (ip or "").strip()
        if not normalized:
            return False
        now = utc_now()
        with self._sf() as db:
            row = (
                db.query(PlatformSecurityIpBanORM)
                .filter(PlatformSecurityIpBanORM.ip == normalized)
                .first()
            )
            if row is None:
                return False
            if row.released_at is not None:
                return False
            if row.expires_at is not None and not self._is_datetime_future(row.expires_at, now=now):
                return False
            return True

    def upsert_ip_ban(
        self,
        *,
        ip: str,
        reason: str | None,
        created_by: int | None,
        expires_at: datetime | None,
    ) -> PlatformSecurityIpBanORM:
        self.ensure_security_storage()
        normalized = ip.strip()
        with self._sf() as db:
            row = db.query(PlatformSecurityIpBanORM).filter(PlatformSecurityIpBanORM.ip == normalized).first()
            if row is None:
                row = PlatformSecurityIpBanORM(
                    ip=normalized,
                    reason=(reason or "").strip() or None,
                    created_by=created_by,
                    expires_at=expires_at,
                    released_at=None,
                    released_by=None,
                )
                db.add(row)
            else:
                row.reason = (reason or "").strip() or row.reason
                row.created_by = created_by
                row.created_at = utc_now()
                row.expires_at = expires_at
                row.released_at = None
                row.released_by = None
            db.commit()
            db.refresh(row)
            return row

    def release_ip_ban(self, ip: str, *, released_by: int | None) -> bool:
        normalized = ip.strip()
        with self._sf() as db:
            row = db.query(PlatformSecurityIpBanORM).filter(PlatformSecurityIpBanORM.ip == normalized).first()
            if row is None:
                return False
            row.released_at = utc_now()
            row.released_by = released_by
            db.commit()
            return True

    def list_ip_bans(self, *, limit: int = 200) -> list[PlatformSecurityIpBanORM]:
        with self._sf() as db:
            return (
                db.query(PlatformSecurityIpBanORM)
                .order_by(PlatformSecurityIpBanORM.created_at.desc())
                .limit(limit)
                .all()
            )

