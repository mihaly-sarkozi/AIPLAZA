# backend/core/modules/auth/use_cases/login_service.py
# Feladat: A felhasználói login application service-t valósítja meg. Kezeli az email+jelszó első lépést, emailes vagy authenticator 2FA challenge-et, token/session kiadást, audit/security logolást, failed login állapotot és trial/tenant security verzió claimet. Auth use case réteg, amely portokon keresztül repositorykra és TokenService-re épül.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations
import base64
import uuid
import hashlib
import hmac
import struct
from urllib.parse import quote
from passlib.hash import bcrypt_sha256 as pwd_hasher
from datetime import datetime, timezone, timedelta
from typing import Optional

from core.modules.auth.domain.dto import (
    LoginInput,
    LoginResult,
    LoginSuccess,
    LoginTwoFactorRequired,
    TenantAuthContext,
)
from core.modules.auth.domain.ports import (
    AuthSessionRepositoryPort,
    AuthUserRepositoryPort,
    DefaultTwoFactorSettingsReader,
    PendingTwoFactorRepositoryPort,
    SecurityLoggerPort,
    TokenServicePort,
    TwoFactorSettingsReader,
)
from core.modules.users.domain.dto import User
from core.modules.auth.domain.dto.session import Session
from core.kernel.logging.security_logger import SecurityLogger
from core.modules.auth.use_cases.two_factor_service import TwoFactorService
from core.modules.auth.domain.exceptions import TwoFactorTooManyAttemptsError
from core.infrastructure.audit.service.audit_service import AuditService
from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.kernel.db.transactional_service import TransactionalServiceMixin
from core.kernel.runtime.clock import Clock, SystemClock
from core.kernel.logging.observability import increment_metric

PENDING_2FA_EXPIRE_MINUTES = 10


class LoginService(TransactionalServiceMixin):
    _ROLE_AUTHENTICATOR_REQUIRED = {"admin", "owner", "platform_admin"}

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        user_repository: AuthUserRepositoryPort,
        session_repository: AuthSessionRepositoryPort,
        pending_2fa_repository: PendingTwoFactorRepositoryPort,
        tokens: TokenServicePort,
        logger: SecurityLoggerPort | SecurityLogger,
        two_factor_service: TwoFactorService,
        audit_service: AuditService,
        two_factor_settings: TwoFactorSettingsReader | None = None,
        user_authenticator_repository=None,
        transaction_manager=None,
        clock: Clock | None = None,
    ):
        super().__init__(transaction_manager=transaction_manager)
        self.user_repository = user_repository
        self.session_repository = session_repository
        self.pending_2fa_repository = pending_2fa_repository
        self.tokens = tokens
        self.logger = logger
        self.two_factor_service = two_factor_service
        if user_authenticator_repository is None:
            class _NoopAuthenticatorRepository:
                def get_enabled_secret(self, user_id: int):
                    return None

                def upsert_pending_secret(self, user_id: int, *, pending_secret_base32: str, pending_expires_at, updated_by: int | None = None):
                    return None

                def get_pending_secret(self, user_id: int):
                    return None

                def enable_secret(self, user_id: int, *, secret_base32: str, updated_by: int | None = None):
                    return None

                def get_by_user_id(self, user_id: int):
                    return None

                def disable(self, user_id: int, *, updated_by: int | None = None):
                    return None

            self.user_authenticator_repository = _NoopAuthenticatorRepository()
        else:
            self.user_authenticator_repository = user_authenticator_repository
        self.audit = audit_service
        self.two_factor_settings = two_factor_settings or DefaultTwoFactorSettingsReader()
        self.clock = clock or SystemClock()

    # Felhasználó bejelentkezés
    def login(self, inp: LoginInput) -> LoginResult:
        """Application réteg: bemenet LoginInput DTO. 1. lépés (email+jelszó) vagy 2. lépés (pending_token+two_factor_code)."""
        with self._transaction():
            tenant = inp.tenant or TenantAuthContext(
                tenant_id=None,
                slug=None,
                correlation_id=None,
                security_version=0,
            )
            if inp.pending_token and inp.two_factor_code:
                return self._login_step2(inp.pending_token, inp.two_factor_code, inp.ip, inp.ua, inp.auto_login, tenant=tenant)
            return self._login_step1(inp.email, inp.password, inp.ip, inp.ua, inp.auto_login, tenant=tenant)

    def issue_tokens_for_user(
        self,
        user: User,
        *,
        ip: str | None,
        ua: str | None,
        auto_login: bool = False,
        tenant: TenantAuthContext,
    ) -> LoginSuccess:
        with self._transaction():
            access, refresh, access_jti = self._issue_tokens(
                user.id,
                ip,
                ua,
                auto_login,
                getattr(user, "security_version", 0),
                tenant.security_version,
                user.role,
            )
            return LoginSuccess(
                access_token=access,
                refresh_token=refresh,
                user=user,
                access_jti=access_jti,
            )

    # Felhasználó bejelentkezés 1. lépés
    def _login_step1(
        self,
        email: Optional[str],
        password: Optional[str],
        ip: str | None,
        ua: str | None,
        auto_login: bool = False,
        *,
        tenant: TenantAuthContext,
    ) -> LoginResult:
        ctx = {"tenant_slug": tenant.slug, "correlation_id": tenant.correlation_id}
        if not email or not password:
            return None
        user = self.user_repository.get_by_email(email)
        # Ha nincs felhasználó akkor hibát dobunk
        if user is None:
            increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "login", "reason": "invalid_user"})
            self.logger.login_invalid_user_attempt(email, ip, ua, **ctx)
            self.audit.log(AuditLogAction.LOGIN_FAILED, user_id=None, details={"reason": "invalid_user", "email": email}, ip=ip, user_agent=ua)
            return None

        # Ha a felhasználó nem aktív akkor hibát dobunk
        if not user.is_active:
            increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "login", "reason": "inactive_user"})
            self.logger.login_inactive_user_attempt(user.id, ip, ua, **ctx)
            self.audit.log(AuditLogAction.LOGIN_FAILED, user_id=user.id, details={"reason": "inactive_user"}, ip=ip, user_agent=ua)
            return None

        # Ha a jelszó nem megfelelő: növeljük a sikertelen próbálkozást, 5 után kilitjuk (is_active=False)
        if not pwd_hasher.verify(password, user.password_hash):
            increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "login", "reason": "bad_password"})
            self.logger.login_bad_password_attempt(user.id, ip, ua, **ctx)
            self.audit.log(
                AuditLogAction.LOGIN_FAILED,
                user_id=user.id,
                details={"reason": "bad_password", "email": email},
                ip=ip,
                user_agent=ua,
            )
            self.user_repository.record_failed_login(user.id, updated_by=user.id)
            return None

        # Jelszó jó: nullázzuk a sikertelen próbálkozások számát
        self.user_repository.reset_failed_login(user.id, updated_by=user.id)

        user_role = str(getattr(user, "role", "") or "").strip().lower()
        require_authenticator_now = user_role in self._ROLE_AUTHENTICATOR_REQUIRED and not bool(tenant.trial_active)
        authenticator_secret = self.user_authenticator_repository.get_enabled_secret(user.id)

        if require_authenticator_now and not authenticator_secret:
            increment_metric(
                "platform.auth.failure.count",
                1.0,
                tags={"flow": "login", "reason": "authenticator_required_not_configured"},
            )
            self.audit.log(
                AuditLogAction.LOGIN_FAILED,
                user_id=user.id,
                details={"reason": "authenticator_required_not_configured", "email": user.email},
                ip=ip,
                user_agent=ua,
            )
            raise ValueError("authenticator_required_setup")

        # Ha nincs semmilyen aktív 2FA kihívás (globális 2FA kikapcsolva, és authenticator sincs),
        # akkor azonnal beléptetés.
        if not self.two_factor_settings.is_two_factor_enabled() and not require_authenticator_now and not authenticator_secret:
            increment_metric("platform.auth.success.count", 1.0, tags={"flow": "login"})
            self.logger.login_successful_login(user.id, ip, ua, **ctx)
            self.audit.log(AuditLogAction.LOGIN_SUCCESS, user_id=user.id, details={"email": user.email, "2fa": False}, ip=ip, user_agent=ua)
            access, refresh, access_jti = self._issue_tokens(user.id, ip, ua, auto_login, getattr(user, "security_version", 0), tenant.security_version, user.role)
            return LoginSuccess(access_token=access, refresh_token=refresh, user=user, access_jti=access_jti)

        # 2FA be van kapcsolva: kódot küldünk, pending_token-t adunk vissza
        if not self.two_factor_service and not authenticator_secret:
            return None

        self.audit.log(AuditLogAction.LOGIN_2FA_REQUIRED, user_id=user.id, details={"email": user.email}, ip=ip, user_agent=ua)
        increment_metric("platform.auth.challenge.count", 1.0, tags={"flow": "login_2fa"})
        pending = uuid.uuid4().hex
        expires_at = self.clock.now() + timedelta(minutes=PENDING_2FA_EXPIRE_MINUTES)
        self.pending_2fa_repository.create(pending, user.id, expires_at, created_by=user.id)
        if not authenticator_secret:
            self.two_factor_service.create_and_send_code(user.id, user.email, pending_token=pending)
            return LoginTwoFactorRequired(pending_token=pending, challenge_type="email")
        return LoginTwoFactorRequired(pending_token=pending, challenge_type="authenticator")


    # Felhasználó bejelentkezés 2. lépés
    def _login_step2(
        self,
        pending_token: str,
        two_factor_code: str,
        ip: str | None,
        ua: str | None,
        auto_login: bool = False,
        *,
        tenant: TenantAuthContext,
    ) -> LoginResult:
        ctx = {"tenant_slug": tenant.slug, "correlation_id": tenant.correlation_id}
        # user_id lekérése consume nélkül (brute-force védelemhez kell a token a verify_code-nak)
        user_id = self.pending_2fa_repository.get_user_id(pending_token)
        if not user_id:
            return None

        # 2FA kód ellenőrzése (limit: pending token / user / IP); túl sok próbálkozás → TwoFactorTooManyAttemptsError
        if not self.two_factor_service:
            return None
        authenticator_secret = self.user_authenticator_repository.get_enabled_secret(user_id)
        try:
            code_ok = False
            if authenticator_secret:
                self._ensure_authenticator_attempt_not_blocked(
                    user_id=user_id,
                    pending_token=pending_token,
                    ip=ip,
                )
                code_ok = self.verify_authenticator_code(authenticator_secret, two_factor_code)
                if not code_ok:
                    blocked_now = self._record_authenticator_failed_attempt(
                        user_id=user_id,
                        pending_token=pending_token,
                        ip=ip,
                    )
                    increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "login_2fa", "reason": "invalid_authenticator_code"})
                    self.logger.login_bad_password_attempt(user_id, ip, ua, **ctx)
                    self.audit.log(
                        AuditLogAction.LOGIN_2FA_FAILED,
                        user_id=user_id,
                        details={"reason": "invalid_authenticator_code"},
                        ip=ip,
                        user_agent=ua,
                    )
                    if blocked_now:
                        raise TwoFactorTooManyAttemptsError()
                    return None
                self._reset_authenticator_attempts(
                    user_id=user_id,
                    pending_token=pending_token,
                    ip=ip,
                )
            else:
                code_ok = self.two_factor_service.verify_code(
                    user_id, two_factor_code, pending_token=pending_token, ip=ip
                )
            if not code_ok:
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "login_2fa", "reason": "invalid_code"})
                self.logger.login_bad_password_attempt(user_id, ip, ua, **ctx)
                self.audit.log(AuditLogAction.LOGIN_2FA_FAILED, user_id=user_id, details={"reason": "invalid_code"}, ip=ip, user_agent=ua)
                return None
        except TwoFactorTooManyAttemptsError:
            try:
                self.pending_2fa_repository.consume(pending_token)
            except Exception:
                pass
            increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "login_2fa", "reason": "rate_limited"})
            self.audit.log(AuditLogAction.LOGIN_2FA_RATE_LIMITED, user_id=user_id, details={"reason": "too_many_attempts"}, ip=ip, user_agent=ua)
            raise

        # Sikeres 2FA: pending token consume (egy használat)
        self.pending_2fa_repository.consume(pending_token)

        # Betöltjük az azonosított felhasználót
        user = self.user_repository.get_by_id(user_id)

        # Ha nincs felhasználó vagy nem aktív akkor hibát dobunk
        if not user or not user.is_active:
            return None

        self.logger.login_successful_login(user.id, ip, ua, **ctx)
        increment_metric("platform.auth.success.count", 1.0, tags={"flow": "login_2fa"})
        self.audit.log(
            AuditLogAction.LOGIN_2FA_SUCCESS,
            user_id=user.id,
            details={"email": user.email, "challenge_type": "authenticator" if authenticator_secret else "email"},
            ip=ip,
            user_agent=ua,
        )
        self.audit.log(AuditLogAction.LOGIN_SUCCESS, user_id=user.id, details={"email": user.email}, ip=ip, user_agent=ua)
        access, refresh, access_jti = self._issue_tokens(user.id, ip, ua, auto_login, getattr(user, "security_version", 0), tenant.security_version, user.role)
        return LoginSuccess(access_token=access, refresh_token=refresh, user=user, access_jti=access_jti)

    def _authenticator_attempt_policy(self) -> tuple[object | None, int, int]:
        two_factor = self.two_factor_service
        attempt_repo = getattr(two_factor, "attempt_repo", None) if two_factor else None
        max_attempts = max(1, int(getattr(two_factor, "max_attempts", 5) or 5))
        window_minutes = max(1, int(getattr(two_factor, "attempt_window_minutes", 15) or 15))
        return attempt_repo, max_attempts, window_minutes

    @staticmethod
    def _authenticator_attempt_scopes(*, user_id: int, pending_token: str | None, ip: str | None) -> list[tuple[str, str]]:
        return [
            ("token", str(pending_token or "").strip()),
            ("user", str(user_id)),
            ("ip", str(ip or "").strip()),
        ]

    def _ensure_authenticator_attempt_not_blocked(self, *, user_id: int, pending_token: str | None, ip: str | None) -> None:
        attempt_repo, max_attempts, window_minutes = self._authenticator_attempt_policy()
        if attempt_repo is None:
            return
        for scope, key in self._authenticator_attempt_scopes(user_id=user_id, pending_token=pending_token, ip=ip):
            if key and attempt_repo.is_blocked(scope, key, max_attempts, window_minutes):
                raise TwoFactorTooManyAttemptsError()

    def _record_authenticator_failed_attempt(self, *, user_id: int, pending_token: str | None, ip: str | None) -> bool:
        attempt_repo, max_attempts, window_minutes = self._authenticator_attempt_policy()
        if attempt_repo is None:
            return False
        blocked_now = False
        for scope, key in self._authenticator_attempt_scopes(user_id=user_id, pending_token=pending_token, ip=ip):
            if not key:
                continue
            attempt_repo.record_failed(scope, key, window_minutes, actor_user_id=user_id)
            if attempt_repo.is_blocked(scope, key, max_attempts, window_minutes):
                blocked_now = True
        return blocked_now

    def _reset_authenticator_attempts(self, *, user_id: int, pending_token: str | None, ip: str | None) -> None:
        attempt_repo, _, _ = self._authenticator_attempt_policy()
        if attempt_repo is None:
            return
        attempt_repo.reset_for_success(
            pending_token_key=str(pending_token or ""),
            user_id=user_id,
            ip=ip,
            actor_user_id=user_id,
        )

    @staticmethod
    def _sanitize_totp_secret(secret: str) -> str:
        return "".join(ch for ch in (secret or "").upper() if ch.isalnum())

    @classmethod
    def _hotp(cls, secret: str, counter: int, digits: int = 6) -> str:
        key = base64.b32decode(cls._sanitize_totp_secret(secret), casefold=True)
        msg = struct.pack(">Q", int(counter))
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
        token = binary % (10 ** digits)
        return str(token).zfill(digits)

    @classmethod
    def verify_authenticator_code(cls, secret: str, code: str, *, period_sec: int = 30, window: int = 1) -> bool:
        normalized_code = "".join(ch for ch in (code or "") if ch.isdigit())
        if len(normalized_code) != 6:
            return False
        now_counter = int(datetime.now(timezone.utc).timestamp() // period_sec)
        for delta in range(-window, window + 1):
            if cls._hotp(secret, now_counter + delta) == normalized_code:
                return True
        return False

    @staticmethod
    def _base32_secret(byte_length: int = 20) -> str:
        raw = uuid.uuid4().bytes + uuid.uuid4().bytes
        return base64.b32encode(raw[:byte_length]).decode("ascii").rstrip("=")

    def start_authenticator_setup(self, user_id: int, user_email: str, *, issuer: str = "AIPLAZA") -> dict:
        secret = self._base32_secret()
        expires_at = self.clock.now() + timedelta(minutes=10)
        self.user_authenticator_repository.upsert_pending_secret(
            user_id,
            pending_secret_base32=secret,
            pending_expires_at=expires_at,
            updated_by=user_id,
        )
        account_name = (user_email or "").strip() or f"user-{user_id}"
        issuer_value = quote((issuer or "AIPLAZA").strip(), safe="")
        account_value = quote(account_name, safe="")
        otpauth_uri = (
            f"otpauth://totp/{issuer_value}:{account_value}"
            f"?secret={secret}&issuer={issuer_value}&algorithm=SHA1&digits=6&period=30"
        )
        return {
            "enabled": False,
            "pending": True,
            "secret": secret,
            "otpauth_uri": otpauth_uri,
            "expires_at": expires_at.isoformat(),
        }

    def confirm_authenticator_setup(self, user_id: int, code: str) -> dict:
        pending_secret = self.user_authenticator_repository.get_pending_secret(user_id)
        if not pending_secret:
            raise ValueError("authenticator_setup_not_started")
        if not self.verify_authenticator_code(pending_secret, code):
            raise ValueError("invalid_authenticator_code")
        self.user_authenticator_repository.enable_secret(user_id, secret_base32=pending_secret, updated_by=user_id)
        self.user_repository.increment_security_version(user_id, updated_by=user_id)
        self.session_repository.invalidate_all_for_user(user_id, updated_by=user_id)
        return {"enabled": True, "pending": False}

    def authenticator_status(self, user_id: int) -> dict:
        row = self.user_authenticator_repository.get_by_user_id(user_id)
        now_utc = self._as_utc_aware(self.clock.now())
        pending_expires_at = self._as_utc_aware(getattr(row, "pending_expires_at", None)) if row else None
        pending = bool(row and row.pending_secret_base32 and pending_expires_at and pending_expires_at > now_utc)
        enabled = bool(row and row.is_enabled and row.secret_base32)
        return {"enabled": enabled, "pending": pending}

    def disable_authenticator(self, user_id: int) -> None:
        self.user_authenticator_repository.disable(user_id, updated_by=user_id)
        self.user_repository.increment_security_version(user_id, updated_by=user_id)
        self.session_repository.invalidate_all_for_user(user_id, updated_by=user_id)

    @staticmethod
    def _as_utc_aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


    # Tokens előállítása
    def _issue_tokens(
        self,
        user_id: int,
        ip: str | None,
        ua: str | None,
        auto_login: bool = False,
        user_ver: int = 0,
        tenant_ver: int = 0,
        role: str = "user",
    ) -> tuple[str, str, str]:
        # Érvénytelenítjük a már létező session-eket
        self.session_repository.invalidate_all_for_user(user_id, updated_by=user_id)
        # Generáljuk a refresh token-t és a claims-et (al=auto_login a cookie max_age-hoz; user_ver/tenant_ver = force revoke)
        refresh, claims = self.tokens.make_refresh_pair(user_id, auto_login=auto_login, user_ver=user_ver, tenant_ver=tenant_ver)
        
        # A claims-ból kivesszük a lejárati időt
        exp_val = claims["exp"]
        exp_dt = exp_val if isinstance(exp_val, datetime) else datetime.fromtimestamp(exp_val, tz=timezone.utc)
        
        # Hash-eljük a refresh token-t
        hashed_refresh = self.tokens.hash_token(refresh)
        
        # Létrehozunk egy új session-t
        s = Session.new(
            user_id=user_id,
            jti=claims["jti"],
            token_hash=hashed_refresh,
            expires_at=exp_dt,
            ip=ip,
            user_agent=ua,
        )
        
        # Elmentjük a session-t a DB-ben
        self.session_repository.create(s, created_by=user_id)
        
        # Generáljuk az access token-t (jti a token_allowlisthez; user_ver/tenant_ver/role = force revoke + token-driven auth)
        access, access_jti = self.tokens.make_access(user_id, user_ver=user_ver, tenant_ver=tenant_ver, role=role)
        return access, refresh, access_jti
