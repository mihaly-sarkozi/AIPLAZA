# backend/admin/service/platform_admin_service.py
# Feladat: A platform-admin modul üzleti műveleteit tartalmazza. Kezeli az első admin bootstrapet, login/refresh tokeneket, MFA setup/confirm/disable folyamatot, admin user CRUD-ot, IP tiltást, monitoring adatokat és alert acknowledgementet. Admin service réteg, amely repositoryra, token service-re és email service-re épül.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import hashlib
import json
import secrets
import csv
import io
from email.utils import parseaddr
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt
from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.modules.auth.domain.dto.session import Session
from core.infrastructure.email.email_service import EmailService
from core.modules.auth.use_cases.login_service import LoginService
from core.modules.users.service._user_service_helpers import new_invite_token_payload
from core.kernel.runtime.clock import utc_now
from core.kernel.config.config_loader import settings
from core.modules.auth.repository.token_allowlist import remove_by_user as allowlist_remove_by_user
from core.modules.auth.service.token_service import TokenService
from admin.domain.admin_models import PlatformAdminUserORM
from admin.repository.platform_admin_repository import PlatformAdminRepository
from shared.validation.password import validate_password_strength


def normalize_email(email: str) -> str:
    parsed = parseaddr((email or "").strip())[1].strip().lower()
    return parsed


def ensure_valid_email(email: str) -> str:
    normalized = normalize_email(email)
    if not normalized or "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
        raise ValueError("invalid_email")
    return normalized


def platform_admin_set_password_link(request_base_url: str | None, token: str) -> str:
    base = (settings.frontend_base_url or request_base_url or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/platform-admin/set-password?token={token}"


class PlatformAdminService:
    def __init__(
        self,
        *,
        repository: PlatformAdminRepository,
        token_service: TokenService,
        email_service: EmailService | None = None,
    ) -> None:
        self.repository = repository
        self.token_service = token_service
        self.email_service = email_service

    def bootstrap_first_admin(self) -> None:
        self.repository.ensure_security_storage()
        email = normalize_email(getattr(settings, "platform_admin_bootstrap_email", ""))
        password = getattr(settings, "platform_admin_bootstrap_password", "")
        if not email or not password:
            return
        if self.repository.get_by_email(email):
            return
        ok, message = validate_password_strength(password)
        if not ok:
            raise ValueError(f"Invalid platform admin bootstrap password: {message}")
        self.repository.create_user(
            email=email,
            name="Platform admin",
            password_hash=pwd_hasher.hash(password),
            is_active=True,
            registration_completed_at=utc_now(),
        )

    def user_to_response(self, user: PlatformAdminUserORM) -> dict:
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role or "admin",
            "is_active": bool(user.is_active),
            "created_at": user.created_at,
            "deleted_at": user.deleted_at,
            "pending_registration": user.registration_completed_at is None and user.deleted_at is None,
            "mfa_enabled": bool(getattr(user, "mfa_enabled", False)),
        }

    @staticmethod
    def _normalize_mfa_code(value: str | None) -> str:
        return "".join(ch for ch in (value or "") if ch.isalnum()).upper()

    @staticmethod
    def _new_recovery_codes(count: int = 8) -> list[str]:
        return [secrets.token_hex(4).upper() for _ in range(max(1, count))]

    @staticmethod
    def _recovery_hash(code: str) -> str:
        return hashlib.sha256(str(code or "").strip().upper().encode("utf-8")).hexdigest()

    def _is_platform_admin_mfa_enabled(self, user: PlatformAdminUserORM) -> bool:
        return bool(getattr(user, "mfa_enabled", False) and getattr(user, "mfa_secret_base32", None))

    @staticmethod
    def _mfa_attempt_kind_from_code(code: str | None) -> str:
        normalized = PlatformAdminService._normalize_mfa_code(code)
        return "recovery" if len(normalized) >= 8 else "totp"

    @staticmethod
    def _normalized_ip(ip: str | None) -> str:
        return str(ip or "unknown").strip()[:64] or "unknown"

    @staticmethod
    def _mfa_attempt_scope_pairs(user_id: int, ip: str | None, *, kind: str) -> list[tuple[str, str]]:
        suffix = "recovery" if kind == "recovery" else "totp"
        safe_ip = PlatformAdminService._normalized_ip(ip)
        return [
            (f"platform_admin_mfa_{suffix}_user", str(user_id)),
            (f"platform_admin_mfa_{suffix}_ip", safe_ip),
        ]

    @staticmethod
    def _platform_admin_mfa_policy() -> dict[str, int]:
        return {
            "attempt_window_minutes": max(1, int(getattr(settings, "platform_admin_mfa_attempt_window_minutes", 15) or 15)),
            "lock_minutes": max(1, int(getattr(settings, "platform_admin_mfa_lock_minutes", 30) or 30)),
            "totp_user_max_attempts": max(1, int(getattr(settings, "platform_admin_mfa_totp_max_attempts_per_user", 5) or 5)),
            "totp_ip_max_attempts": max(1, int(getattr(settings, "platform_admin_mfa_totp_max_attempts_per_ip", 10) or 10)),
            "recovery_user_max_attempts": max(
                1, int(getattr(settings, "platform_admin_mfa_recovery_max_attempts_per_user", 3) or 3)
            ),
            "recovery_ip_max_attempts": max(
                1, int(getattr(settings, "platform_admin_mfa_recovery_max_attempts_per_ip", 6) or 6)
            ),
        }

    def _platform_admin_mfa_limit_for_scope(self, *, kind: str, scope: str) -> int:
        policy = self._platform_admin_mfa_policy()
        if kind == "recovery":
            return policy["recovery_ip_max_attempts"] if scope.endswith("_ip") else policy["recovery_user_max_attempts"]
        return policy["totp_ip_max_attempts"] if scope.endswith("_ip") else policy["totp_user_max_attempts"]

    def _ensure_platform_admin_mfa_attempt_not_blocked(self, *, user_id: int, ip: str | None, kind: str) -> None:
        for scope, scope_key in self._mfa_attempt_scope_pairs(user_id, ip, kind=kind):
            if self.repository.is_platform_admin_mfa_scope_blocked(scope=scope, scope_key=scope_key):
                raise ValueError("platform_admin_mfa_locked")

    def _record_platform_admin_mfa_failed_attempt(self, *, user_id: int, ip: str | None, kind: str) -> bool:
        policy = self._platform_admin_mfa_policy()
        blocked_now = False
        for scope, scope_key in self._mfa_attempt_scope_pairs(user_id, ip, kind=kind):
            max_attempts = self._platform_admin_mfa_limit_for_scope(kind=kind, scope=scope)
            if self.repository.record_platform_admin_mfa_failed_attempt(
                scope=scope,
                scope_key=scope_key,
                max_attempts=max_attempts,
                window_minutes=policy["attempt_window_minutes"],
                lock_minutes=policy["lock_minutes"],
                actor_user_id=user_id,
            ):
                blocked_now = True
        return blocked_now

    def _reset_platform_admin_mfa_attempts(self, *, user_id: int, ip: str | None) -> None:
        scopes = (
            self._mfa_attempt_scope_pairs(user_id, ip, kind="totp")
            + self._mfa_attempt_scope_pairs(user_id, ip, kind="recovery")
        )
        self.repository.reset_platform_admin_mfa_attempts(scopes=scopes, actor_user_id=user_id)

    def _send_platform_admin_lock_alert(self, *, user: PlatformAdminUserORM, ip: str | None, ua: str | None, reason: str) -> None:
        recipient = str(getattr(settings, "platform_admin_login_alert_email", "") or "").strip()
        if not recipient or not self.email_service:
            return
        try:
            subject = "AIPLAZA platform admin security alert"
            body = (
                "Platform admin MFA lockout esemény történt.\n\n"
                f"Email: {user.email}\n"
                f"Ok: {reason}\n"
                f"IP: {ip or 'unknown'}\n"
                f"User-Agent: {ua or 'unknown'}\n"
                f"Időpont (UTC): {utc_now().isoformat()}\n"
            )
            self.email_service.send_email(recipient, subject, body)
        except Exception:
            pass

    def _verify_platform_admin_mfa(self, user: PlatformAdminUserORM, code: str | None) -> bool:
        normalized = self._normalize_mfa_code(code)
        if not normalized:
            return False
        secret = str(getattr(user, "mfa_secret_base32", "") or "").strip()
        if secret and LoginService.verify_authenticator_code(secret, normalized):
            return True
        if len(normalized) >= 8:
            return self.repository.consume_mfa_recovery_code(
                user.id,
                code_hash=self._recovery_hash(normalized),
                updated_by=user.id,
            )
        return False

    def mfa_status(self, user_id: int) -> dict:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise ValueError("user_not_found")
        pending = bool(
            getattr(user, "mfa_pending_secret_base32", None)
            and getattr(user, "mfa_pending_expires_at", None)
            and getattr(user, "mfa_pending_expires_at", None) > utc_now()
        )
        hashes_raw = str(getattr(user, "mfa_recovery_codes_hashes", "[]") or "[]")
        try:
            remaining = len([v for v in json.loads(hashes_raw) if str(v).strip()])
        except Exception:
            remaining = 0
        return {
            "enabled": self._is_platform_admin_mfa_enabled(user),
            "pending": pending,
            "recovery_codes_remaining": remaining,
        }

    def start_mfa_setup(self, user_id: int, *, issuer: str = "AIPLAZA Platform Admin") -> dict:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise ValueError("user_not_found")
        secret = LoginService._base32_secret()
        expires_at = utc_now() + timedelta(minutes=10)
        updated = self.repository.upsert_pending_mfa_secret(
            user_id,
            pending_secret_base32=secret,
            pending_expires_at=expires_at,
            updated_by=user_id,
        )
        if updated is None:
            raise ValueError("user_not_found")
        account_name = (user.email or "").strip() or f"platform-admin-{user_id}"
        issuer_value = quote((issuer or "AIPLAZA Platform Admin").strip(), safe="")
        account_value = quote(account_name, safe="")
        otpauth_uri = (
            f"otpauth://totp/{issuer_value}:{account_value}"
            f"?secret={secret}&issuer={issuer_value}&algorithm=SHA1&digits=6&period=30"
        )
        return {
            "enabled": self._is_platform_admin_mfa_enabled(updated),
            "pending": True,
            "secret": secret,
            "otpauth_uri": otpauth_uri,
            "expires_at": expires_at.isoformat(),
        }

    def confirm_mfa_setup(self, user_id: int, *, code: str) -> dict:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise ValueError("user_not_found")
        pending_secret = str(getattr(user, "mfa_pending_secret_base32", "") or "").strip()
        pending_expires_at = getattr(user, "mfa_pending_expires_at", None)
        if not pending_secret or pending_expires_at is None or pending_expires_at <= utc_now():
            raise ValueError("mfa_setup_not_started")
        if not LoginService.verify_authenticator_code(pending_secret, code):
            raise ValueError("invalid_mfa_code")
        recovery_codes = self._new_recovery_codes()
        updated = self.repository.enable_mfa(
            user_id,
            secret_base32=pending_secret,
            recovery_code_hashes=[self._recovery_hash(code_value) for code_value in recovery_codes],
            updated_by=user_id,
        )
        if updated is None:
            raise ValueError("user_not_found")
        self.repository.invalidate_all_refresh_sessions_for_user(user_id, updated_by=user_id)
        return {"enabled": True, "pending": False, "recovery_codes": recovery_codes}

    def disable_mfa(self, user_id: int, *, password: str) -> None:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise ValueError("user_not_found")
        if not pwd_hasher.verify(password or "", user.password_hash):
            raise ValueError("invalid_password")
        if self.repository.disable_mfa(user_id, updated_by=user_id) is None:
            raise ValueError("user_not_found")
        self.repository.invalidate_all_refresh_sessions_for_user(user_id, updated_by=user_id)

    def _issue_access_and_refresh(
        self,
        user: PlatformAdminUserORM,
        *,
        ip: str | None,
        ua: str | None,
    ) -> tuple[str, str, str]:
        access_token, access_jti = self.token_service.make_platform_admin_access(
            user.id,
            user_ver=int(user.security_version or 0),
            role=user.role or "admin",
        )
        refresh_token, refresh_claims = self.token_service.make_platform_admin_refresh_pair(
            user.id,
            user_ver=int(user.security_version or 0),
        )
        exp = refresh_claims["exp"]
        exp_dt = exp if isinstance(exp, datetime) else datetime.fromtimestamp(exp, tz=timezone.utc)
        self.repository.create_refresh_session(
            Session.new(
                user_id=user.id,
                jti=refresh_claims["jti"],
                token_hash=self.token_service.hash_token(refresh_token),
                expires_at=exp_dt,
                ip=ip,
                user_agent=ua,
            ),
            created_by=user.id,
        )
        return access_token, refresh_token, access_jti

    def login(
        self,
        email: str,
        password: str,
        *,
        ip: str | None = None,
        ua: str | None = None,
        mfa_code: str | None = None,
    ) -> tuple[str, str, str, PlatformAdminUserORM] | None:
        user = self.repository.get_by_email(normalize_email(email))
        if not user or not user.is_active or user.deleted_at is not None:
            return None
        if not pwd_hasher.verify(password, user.password_hash):
            failures = int(user.failed_login_attempts or 0) + 1
            lock_threshold = max(1, int(getattr(settings, "platform_admin_max_failed_login_attempts", 8)))
            should_lock = failures >= lock_threshold
            self.repository.update_user(
                user.id,
                failed_login_attempts=failures,
                is_active=False if should_lock else None,
                bump_security_version=should_lock,
                updated_by=user.id,
            )
            return None
        if self._is_platform_admin_mfa_enabled(user):
            if not self._normalize_mfa_code(mfa_code):
                raise ValueError("platform_admin_mfa_required")
            attempt_kind = self._mfa_attempt_kind_from_code(mfa_code)
            self._ensure_platform_admin_mfa_attempt_not_blocked(user_id=user.id, ip=ip, kind=attempt_kind)
            if not self._verify_platform_admin_mfa(user, mfa_code):
                blocked_now = self._record_platform_admin_mfa_failed_attempt(user_id=user.id, ip=ip, kind=attempt_kind)
                if blocked_now:
                    self.repository.invalidate_all_refresh_sessions_for_user(user.id, updated_by=user.id)
                    try:
                        allowlist_remove_by_user(None, user.id)
                    except Exception:
                        pass
                    self._send_platform_admin_lock_alert(
                        user=user,
                        ip=ip,
                        ua=ua,
                        reason=f"mfa_{attempt_kind}_lockout",
                    )
                    raise ValueError("platform_admin_mfa_locked")
                raise ValueError("platform_admin_mfa_invalid")
            self._reset_platform_admin_mfa_attempts(user_id=user.id, ip=ip)
        updated = self.repository.update_user(user.id, failed_login_attempts=0) or user
        access_token, refresh_token, access_jti = self._issue_access_and_refresh(updated, ip=ip, ua=ua)
        alert_recipient = str(getattr(settings, "platform_admin_login_alert_email", "") or "").strip()
        if alert_recipient and self.email_service:
            try:
                subject = "AIPLAZA platform admin login alert"
                body = (
                    "Sikeres platform-admin bejelentkezés történt.\n\n"
                    f"Email: {updated.email}\n"
                    f"IP: {ip or 'unknown'}\n"
                    f"User-Agent: {ua or 'unknown'}\n"
                    f"Időpont (UTC): {utc_now().isoformat()}\n"
                )
                self.email_service.send_email(alert_recipient, subject, body)
            except Exception:
                pass
        return access_token, refresh_token, access_jti, updated

    def refresh(self, refresh_token: str, *, ip: str | None = None, ua: str | None = None) -> tuple[str, str, str, PlatformAdminUserORM] | None:
        try:
            payload = self.token_service.verify(refresh_token)
        except jwt.InvalidTokenError:
            return None
        if payload.get("typ") != "platform_admin_refresh":
            return None
        try:
            user_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            return None
        session = self.repository.get_refresh_session_by_jti(str(payload.get("jti") or ""))
        if not session or not session.valid or session.is_expired():
            return None
        if session.token_hash != self.token_service.hash_token(refresh_token):
            self.repository.invalidate_all_refresh_sessions_for_user(session.user_id, updated_by=session.user_id)
            return None
        user = self.repository.get_by_id(user_id)
        if not user or not user.is_active or user.deleted_at is not None:
            return None
        if int(payload.get("user_ver") or 0) != int(user.security_version or 0):
            return None
        self.repository.update_refresh_session(session.invalidate(), updated_by=user.id)
        access_token, new_refresh_token, access_jti = self._issue_access_and_refresh(user, ip=ip, ua=ua)
        return access_token, new_refresh_token, access_jti, user

    def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        payload = self.token_service.decode_ignore_exp(refresh_token)
        if not payload or payload.get("typ") != "platform_admin_refresh":
            return
        session = self.repository.get_refresh_session_by_jti(str(payload.get("jti") or ""))
        if session and session.token_hash == self.token_service.hash_token(refresh_token):
            self.repository.update_refresh_session(session.invalidate(), updated_by=session.user_id)

    def resolve_token(self, token: str) -> PlatformAdminUserORM | None:
        try:
            payload = self.token_service.verify(token)
        except jwt.InvalidTokenError:
            return None
        if payload.get("typ") != "platform_admin_access":
            return None
        try:
            user_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            return None
        user = self.repository.get_by_id(user_id)
        if not user or not user.is_active or user.deleted_at is not None:
            return None
        if int(payload.get("user_ver") or 0) != int(user.security_version or 0):
            return None
        return user

    def verify_access_payload(self, token: str) -> dict | None:
        try:
            payload = self.token_service.verify(token)
        except jwt.InvalidTokenError:
            return None
        if payload.get("typ") != "platform_admin_access":
            return None
        return payload

    def create_user(
        self,
        *,
        email: str,
        name: str,
        request_base_url: str | None,
        created_by: int | None,
    ) -> PlatformAdminUserORM:
        normalized = ensure_valid_email(email)
        if self.repository.get_by_email(normalized):
            raise ValueError("email_already_exists")
        user = self.repository.create_user(
            email=normalized,
            name=name,
            password_hash=pwd_hasher.hash(new_invite_token_payload().raw_token),
            is_active=False,
            registration_completed_at=None,
            created_by=created_by,
        )
        self.send_set_password_email(user.id, request_base_url=request_base_url, updated_by=created_by)
        return user

    def update_user(
        self,
        user_id: int,
        *,
        email: str | None,
        name: str | None,
        is_active: bool | None,
        updated_by: int | None,
    ) -> PlatformAdminUserORM:
        existing = self.repository.get_by_id(user_id)
        if not existing or existing.deleted_at is not None:
            raise ValueError("user_not_found")
        normalized_email = ensure_valid_email(email) if email else None
        if normalized_email and normalized_email != normalize_email(existing.email):
            other = self.repository.get_by_email(normalized_email)
            if other and other.id != user_id:
                raise ValueError("email_already_exists")
        updated = self.repository.update_user(
            user_id,
            email=normalized_email,
            name=name,
            is_active=is_active,
            bump_security_version=is_active is False,
            updated_by=updated_by,
        )
        if not updated:
            raise ValueError("user_not_found")
        return updated

    def delete_user(self, user_id: int, *, current_user_id: int) -> None:
        if user_id == current_user_id:
            raise ValueError("cannot_delete_self")
        if not self.repository.delete_user(user_id, deleted_by=current_user_id):
            raise ValueError("user_not_found")
        self.repository.invalidate_all_refresh_sessions_for_user(user_id, updated_by=current_user_id)

    def update_profile(self, user_id: int, *, name: str) -> PlatformAdminUserORM:
        updated = self.repository.update_user(user_id, name=name, updated_by=user_id)
        if not updated:
            raise ValueError("user_not_found")
        return updated

    def change_password(self, user_id: int, *, current_password: str, new_password: str) -> None:
        user = self.repository.get_by_id(user_id)
        if not user or not pwd_hasher.verify(current_password, user.password_hash):
            raise ValueError("invalid_current_password")
        ok, message = validate_password_strength(new_password)
        if not ok:
            raise ValueError(message)
        self.repository.update_user(
            user_id,
            password_hash=pwd_hasher.hash(new_password),
            bump_security_version=True,
            updated_by=user_id,
        )
        self.repository.invalidate_all_refresh_sessions_for_user(user_id, updated_by=user_id)

    def list_active_tenants(self) -> list[dict]:
        return [
            {
                "id": tenant.id,
                "slug": tenant.slug,
                "name": tenant.name,
                "is_active": bool(tenant.is_active),
                "created_at": tenant.created_at,
            }
            for tenant in self.repository.list_active_tenants()
        ]

    def get_statistics(self) -> dict:
        return self.repository.platform_statistics()

    @staticmethod
    def _ensure_ai_page_name_confirmation(tenant: dict, confirm_name: str) -> None:
        if str(confirm_name or "").strip() != str(tenant.get("name") or "").strip():
            raise ValueError("tenant_confirmation_mismatch")

    def restore_cancelled_tenant(self, tenant_id: int, *, confirm_name: str, admin_user_id: int | None) -> dict:
        statistics = self.repository.platform_tenant_statistics_detail(int(tenant_id))
        if statistics is None:
            raise ValueError("tenant_not_found")
        tenant = dict(statistics.get("tenant") or {})
        self._ensure_ai_page_name_confirmation(tenant, confirm_name)
        restored = self.repository.restore_cancelled_tenant(int(tenant_id), updated_by=admin_user_id)
        if restored is None:
            raise ValueError("tenant_not_found")
        return restored

    def permanently_delete_cancelled_tenant(self, tenant_id: int, *, confirm_name: str, admin_user_id: int | None) -> dict:
        statistics = self.repository.platform_tenant_statistics_detail(int(tenant_id))
        if statistics is None:
            raise ValueError("tenant_not_found")
        tenant = dict(statistics.get("tenant") or {})
        self._ensure_ai_page_name_confirmation(tenant, confirm_name)
        deleted = self.repository.permanently_delete_cancelled_tenant(int(tenant_id), deleted_by=admin_user_id)
        if deleted is None:
            raise ValueError("tenant_not_found")
        return deleted

    def get_security_monitoring(self) -> dict:
        return self.repository.platform_security_monitoring()

    def list_security_alerts(self) -> list[dict]:
        return self.repository.list_security_alerts(limit=200)

    def acknowledge_security_alert(self, alert_id: int, *, admin_user_id: int | None) -> dict:
        row = self.repository.acknowledge_security_alert(int(alert_id), admin_user_id=admin_user_id)
        if row is None:
            raise ValueError("alert_not_found")
        return row

    def is_ip_banned(self, ip: str | None) -> bool:
        try:
            return self.repository.is_ip_banned(ip)
        except Exception:
            return False

    def ban_ip(
        self,
        *,
        ip: str,
        reason: str | None,
        expires_hours: int | None,
        admin_user_id: int | None,
    ) -> dict:
        normalized_ip = (ip or "").strip()
        if not normalized_ip:
            raise ValueError("invalid_ip")
        expires_at = None
        if expires_hours:
            expires_at = utc_now() + timedelta(hours=int(expires_hours))
        row = self.repository.upsert_ip_ban(
            ip=normalized_ip,
            reason=reason,
            created_by=admin_user_id,
            expires_at=expires_at,
        )
        return {
            "ip": row.ip,
            "reason": row.reason,
            "created_at": row.created_at,
            "expires_at": row.expires_at,
            "active": row.released_at is None and (row.expires_at is None or row.expires_at > utc_now()),
        }

    def release_ip_ban(self, ip: str, *, admin_user_id: int | None) -> None:
        if not self.repository.release_ip_ban(ip, released_by=admin_user_id):
            raise ValueError("ip_not_found")

    def get_tenant_statistics_detail(self, tenant_id: int) -> dict:
        detail = self.repository.platform_tenant_statistics_detail(tenant_id)
        if detail is None:
            raise ValueError("tenant_not_found")
        return detail

    def list_tenant_audit_trail(
        self,
        *,
        tenant_id: int,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        email: str | None = None,
        actions: list[str] | tuple[str, ...] | None = None,
    ) -> dict:
        result = self.repository.list_tenant_audit_trail(
            tenant_id=tenant_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            cursor=cursor,
            email=email,
            actions=actions,
        )
        if result is None:
            raise ValueError("tenant_not_found")
        return result

    def export_tenant_audit_trail_csv(
        self,
        *,
        tenant_id: int,
        from_date: str | None = None,
        to_date: str | None = None,
        email: str | None = None,
        actions: list[str] | tuple[str, ...] | None = None,
    ) -> tuple[str, str]:
        result = self.repository.export_tenant_audit_trail(
            tenant_id=tenant_id,
            from_date=from_date,
            to_date=to_date,
            email=email,
            actions=actions,
        )
        if result is None:
            raise ValueError("tenant_not_found")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp",
            "title",
            "summary",
            "action",
            "outcome",
            "actor_email",
            "actor_name",
            "user_id",
            "target_type",
            "target_id",
            "ip",
            "user_agent",
            "details",
        ])
        for item in result["items"]:
            writer.writerow([
                item.get("created_at"),
                item.get("title"),
                item.get("summary"),
                item.get("action"),
                item.get("outcome"),
                item.get("actor_email_masked") or item.get("actor_email"),
                item.get("actor_name"),
                item.get("user_id"),
                item.get("target_type"),
                item.get("target_id"),
                item.get("ip"),
                item.get("user_agent"),
                json.dumps(item.get("details") or {}, ensure_ascii=False),
            ])
        tenant_slug = str((result.get("tenant") or {}).get("slug") or tenant_id)
        return f"audit-trail-{tenant_slug}.csv", "\ufeff" + output.getvalue()

    def validate_set_password_token(self, token: str) -> str:
        record = self.repository.get_invite_token(hashlib.sha256(token.encode()).hexdigest())
        if not record or record.used_at:
            return "invalid"
        if record.expires_at < utc_now():
            return "expired"
        return "valid"

    def set_password(self, token: str, password: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        record = self.repository.get_invite_token(token_hash)
        if not record or record.used_at:
            raise ValueError("invalid_token")
        if record.expires_at < utc_now():
            raise ValueError("expired_token")
        ok, message = validate_password_strength(password)
        if not ok:
            raise ValueError(message)
        self.repository.update_user(
            record.user_id,
            password_hash=pwd_hasher.hash(password),
            is_active=True,
            registration_completed_at=utc_now(),
            failed_login_attempts=0,
            bump_security_version=True,
            updated_by=record.user_id,
        )
        self.repository.mark_invite_used(record.id, updated_by=record.user_id)
        self.repository.invalidate_all_refresh_sessions_for_user(record.user_id, updated_by=record.user_id)

    def send_set_password_email(
        self,
        user_id: int,
        *,
        request_base_url: str | None,
        updated_by: int | None,
    ) -> None:
        user = self.repository.get_by_id(user_id)
        if not user or user.deleted_at is not None:
            raise ValueError("user_not_found")
        payload = new_invite_token_payload()
        self.repository.create_invite_token(
            user_id=user.id,
            token_hash=payload.token_hash,
            expires_at=payload.expires_at,
            created_by=updated_by,
        )
        link = platform_admin_set_password_link(request_base_url, payload.raw_token)
        if link and self.email_service:
            self.email_service.send_set_password_invite(user.email, link)

