# backend/core/modules/auth/use_cases/two_factor_service.py
# Feladat: Emailes 2FA kód generálást, kézbesítést és validációt kezel. Régi kódokat érvénytelenít, új kódot ment, emailt küld vagy outboxba tesz, majd token/user/IP scope alapján brute-force limitet alkalmaz validációkor. Auth use case réteg a kétfaktoros login challenge-hez.
# Sárközi Mihály - 2026.05.21

import secrets
import time
from datetime import timedelta
from core.modules.auth.repository.persistence.two_factor_attempt_repository import TwoFactorAttemptRepository
from core.modules.auth.repository.persistence.two_factor_repository import TwoFactorRepository
from core.kernel.logging.request_timing import record_span
from core.modules.auth.domain.dto.two_factor_code import TwoFactorCode
from core.modules.auth.domain.exceptions import TwoFactorEmailError, TwoFactorTooManyAttemptsError
from lang.messages import ErrorCode
from core.infrastructure.email.email_service import EmailService
from core.kernel.runtime.clock import Clock, SystemClock

# Brute-force védelem: max próbálkozás / ablak (pending token, user, IP alapján)
TWO_FA_MAX_ATTEMPTS = 5
TWO_FA_ATTEMPT_WINDOW_MINUTES = 15


# 2FA kód generálás és validálás + brute-force limit
class TwoFactorService:
    
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        two_factor_repo: TwoFactorRepository,
        email_service: EmailService,
        attempt_repo: TwoFactorAttemptRepository | None = None,
        max_attempts: int = TWO_FA_MAX_ATTEMPTS,
        attempt_window_minutes: int = TWO_FA_ATTEMPT_WINDOW_MINUTES,
        code_expiry_minutes: int = 10,
        event_channel: object | None = None,
        clock: Clock | None = None,
    ):
        self.two_factor_repo = two_factor_repo
        self.email_service = email_service
        self.attempt_repo = attempt_repo
        self.max_attempts = max_attempts
        self.attempt_window_minutes = attempt_window_minutes
        self.code_expiry_minutes = code_expiry_minutes
        # Ha van event_channel (async audit), 2FA email háttérbe megy → login step1 nem vár SMTP-re
        self.event_channel = event_channel
        self.clock = clock or SystemClock()
    
    
    # 6 jegyű kriptográfiailag biztonságos véletlen kód (secrets modul)
    def generate_code(self) -> str:
        return f"{secrets.randbelow(900_000) + 100_000}"
    
    # 2FA kód létrehozása és emailben küldése
    def create_and_send_code(self, user_id: int, email: str, pending_token: str | None = None) -> TwoFactorCode:
        
        # Régi kódok érvénytelenítése
        self.two_factor_repo.invalidate_user_codes(user_id, updated_by=user_id)
        
        # Új kód generálása
        code = self.generate_code()
        expires_at = self.clock.now() + timedelta(minutes=self.code_expiry_minutes)
        
        two_factor_code = TwoFactorCode.new(
            user_id=user_id,
            code=code,
            email=email,
            expires_at=expires_at
        )
        
        # Kód mentése
        saved_code = self.two_factor_repo.create(two_factor_code, created_by=user_id)

        # Email: háttérbe (queue) vagy szinkron. Háttérrel login step1 nem vár SMTP-re.
        if self.event_channel and hasattr(self.event_channel, "enqueue_email_2fa"):
            self.event_channel.enqueue_email_2fa(email, code, pending_token=pending_token)
            record_span("email_queued", 0.0)
            return saved_code
        try:
            t0_email = time.monotonic()
            ok = self.email_service.send_2fa_code(email, code, pending_token=pending_token)
            record_span("email_send", (time.monotonic() - t0_email) * 1000)
            if not ok:
                raise TwoFactorEmailError(error_code=ErrorCode.TWO_FACTOR_EMAIL_FAILED)
        except TwoFactorEmailError:
            raise
        except (OSError, RuntimeError, ValueError) as e:
            raise TwoFactorEmailError(str(e), error_code=ErrorCode.TWO_FACTOR_EMAIL_FAILED) from e
        return saved_code
    
    # 2FA kód ellenőrzése
    def verify_code(
        self,
        user_id: int,
        code: str,
        pending_token: str | None = None,
        ip: str | None = None,
    ) -> bool:
        """2FA kód ellenőrzése. Brute-force: max_attempts / token, user, IP. Túl sok próbálkozás → TwoFactorTooManyAttemptsError."""
        if self.attempt_repo:
            scopes = [
                ("token", pending_token or ""),
                ("user", str(user_id)),
                ("ip", ip or ""),
            ]
            for scope, key in scopes:
                if key and self.attempt_repo.is_blocked(
                    scope, key, self.max_attempts, self.attempt_window_minutes
                ):
                    raise TwoFactorTooManyAttemptsError()

        valid_code = self.two_factor_repo.get_valid_code(user_id, code)

        if not valid_code:
            if self.attempt_repo and (pending_token or ip is not None):
                for scope, key in [("token", pending_token or ""), ("user", str(user_id)), ("ip", ip or "")]:
                    if key:
                        self.attempt_repo.record_failed(
                            scope, key, self.attempt_window_minutes, actor_user_id=user_id
                        )
            return False

        if self.attempt_repo:
            self.attempt_repo.reset_for_success(
                pending_token_key=pending_token or "",
                user_id=user_id,
                ip=ip,
                actor_user_id=user_id,
            )
        self.two_factor_repo.mark_as_used(valid_code.id, updated_by=user_id)
        return True
