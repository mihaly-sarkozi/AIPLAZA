# Felhasználó bejelentkezés üzleti logikája
# 1. lépés: email + jelszó → megkeressük, ellenőrizzük; kódot küldünk, vissza TwoFactorRequired(pending_token).
# 2. lépés 2FA esetén!: pending_token + two_factor_code → validáljuk; ha jó → beléptetjük, vissza LoginSuccess.
# 2026.02.28 - Sárközi Mihály

from __future__ import annotations
import uuid
from passlib.hash import bcrypt_sha256 as pwd_hasher
from datetime import datetime, timezone, timedelta
from typing import Optional

from core.capabilities.auth.dto import (
    LoginInput,
    LoginResult,
    LoginSuccess,
    LoginTwoFactorRequired,
    TenantAuthContext,
)
from core.capabilities.auth.ports import (
    AuthSessionRepositoryPort,
    AuthUserRepositoryPort,
    DefaultTwoFactorSettingsReader,
    PendingTwoFactorRepositoryPort,
    SecurityLoggerPort,
    TokenServicePort,
    TwoFactorSettingsReader,
)
from core.capabilities.users.dto import User
from core.capabilities.auth.dto.session import Session
from core.kernel.logging.security_logger import SecurityLogger
from core.capabilities.auth.service.two_factor_service import TwoFactorService
from core.capabilities.auth.exceptions import TwoFactorTooManyAttemptsError
from core.capabilities.audit.service.audit_service import AuditService
from core.capabilities.audit.const.audit_log_action_const import AuditLogAction
from core.kernel.db.transactional_service import TransactionalServiceMixin
from core.kernel.clock import Clock, SystemClock
from core.kernel.logging.observability import increment_metric

PENDING_2FA_EXPIRE_MINUTES = 10


class LoginService(TransactionalServiceMixin):

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
            self.audit.log(AuditLogAction.LOGIN_FAILED, user_id=user.id, details={"reason": "bad_password"}, ip=ip, user_agent=ua)
            self.user_repository.record_failed_login(user.id, updated_by=user.id)
            return None

        # Jelszó jó: nullázzuk a sikertelen próbálkozások számát
        self.user_repository.reset_failed_login(user.id, updated_by=user.id)

        # Ha 2FA ki van kapcsolva: azonnal beléptetés, email megerősítés nélkül
        if not self.two_factor_settings.is_two_factor_enabled():
            increment_metric("platform.auth.success.count", 1.0, tags={"flow": "login"})
            self.logger.login_successful_login(user.id, ip, ua, **ctx)
            self.audit.log(AuditLogAction.LOGIN_SUCCESS, user_id=user.id, details={"email": user.email, "2fa": False}, ip=ip, user_agent=ua)
            access, refresh, access_jti = self._issue_tokens(user.id, ip, ua, auto_login, getattr(user, "security_version", 0), tenant.security_version, user.role)
            return LoginSuccess(access_token=access, refresh_token=refresh, user=user, access_jti=access_jti)

        # 2FA be van kapcsolva: kódot küldünk, pending_token-t adunk vissza
        if not self.two_factor_service:
            return None

        self.audit.log(AuditLogAction.LOGIN_2FA_REQUIRED, user_id=user.id, details={"email": user.email}, ip=ip, user_agent=ua)
        increment_metric("platform.auth.challenge.count", 1.0, tags={"flow": "login_2fa"})
        pending = uuid.uuid4().hex
        expires_at = self.clock.now() + timedelta(minutes=PENDING_2FA_EXPIRE_MINUTES)
        self.pending_2fa_repository.create(pending, user.id, expires_at, created_by=user.id)
        self.two_factor_service.create_and_send_code(user.id, user.email, pending_token=pending)
        return LoginTwoFactorRequired(pending_token=pending)


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
        try:
            if not self.two_factor_service.verify_code(
                user_id, two_factor_code, pending_token=pending_token, ip=ip
            ):
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "login_2fa", "reason": "invalid_code"})
                self.logger.login_bad_password_attempt(user_id, ip, ua, **ctx)
                self.audit.log(AuditLogAction.LOGIN_2FA_FAILED, user_id=user_id, details={"reason": "invalid_code"}, ip=ip, user_agent=ua)
                return None
        except TwoFactorTooManyAttemptsError:
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
        self.audit.log(AuditLogAction.LOGIN_SUCCESS, user_id=user.id, details={"email": user.email}, ip=ip, user_agent=ua)
        access, refresh, access_jti = self._issue_tokens(user.id, ip, ua, auto_login, getattr(user, "security_version", 0), tenant.security_version, user.role)
        return LoginSuccess(access_token=access, refresh_token=refresh, user=user, access_jti=access_jti)


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
