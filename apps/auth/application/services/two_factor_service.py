# apps/auth/application/services/two_factor_service.py
# Kétfaktoros autentikáció szolgáltatás
# 2026.02.28 - Sárközi Mihály

import secrets
from datetime import datetime, timedelta, timezone
from apps.auth.ports import TwoFactorRepositoryInterface, TwoFactorAttemptRepositoryInterface
from apps.auth.domain.two_factor_code import TwoFactorCode
from apps.auth.application.exceptions import TwoFactorEmailError, TwoFactorTooManyAttemptsError
from apps.core.i18n.messages import ErrorCode
from apps.core.email.email_service import EmailService

# Brute-force védelem: max próbálkozás / ablak (pending token, user, IP alapján)
TWO_FA_MAX_ATTEMPTS = 5
TWO_FA_ATTEMPT_WINDOW_MINUTES = 15


class TwoFactorService:
    # 2FA kód generálás és validálás + brute-force limit
    
    def __init__(
        self,
        two_factor_repo: TwoFactorRepositoryInterface,
        email_service: EmailService,
        attempt_repo: TwoFactorAttemptRepositoryInterface | None = None,
        max_attempts: int = TWO_FA_MAX_ATTEMPTS,
        attempt_window_minutes: int = TWO_FA_ATTEMPT_WINDOW_MINUTES,
    ):
        self.two_factor_repo = two_factor_repo
        self.email_service = email_service
        self.attempt_repo = attempt_repo
        self.max_attempts = max_attempts
        self.attempt_window_minutes = attempt_window_minutes
        self.code_expiry_minutes = 10
    
    def generate_code(self) -> str:
        # 6 jegyű kriptográfiailag biztonságos véletlen kód (secrets modul)
        return f"{secrets.randbelow(900_000) + 100_000}"
    
    def create_and_send_code(self, user_id: int, email: str, pending_token: str | None = None) -> TwoFactorCode:
        
        # Régi kódok érvénytelenítése
        self.two_factor_repo.invalidate_user_codes(user_id)
        
        # Új kód generálása
        code = self.generate_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.code_expiry_minutes)
        
        two_factor_code = TwoFactorCode.new(
            user_id=user_id,
            code=code,
            email=email,
            expires_at=expires_at
        )
        
        # Kód mentése
        saved_code = self.two_factor_repo.create(two_factor_code)

        # Email küldése: 2FA kód + pending_token (mindkettő emailben); hiba esetén kód a router i18n-hez
        try:
            ok = self.email_service.send_2fa_code(email, code, pending_token=pending_token)
            if not ok:
                raise TwoFactorEmailError(error_code=ErrorCode.TWO_FACTOR_EMAIL_FAILED)
        except TwoFactorEmailError:
            raise
        except Exception as e:
            raise TwoFactorEmailError(str(e), error_code=ErrorCode.TWO_FACTOR_EMAIL_FAILED) from e

        return saved_code
    
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
                            scope, key, self.attempt_window_minutes
                        )
            return False

        if self.attempt_repo:
            self.attempt_repo.reset_for_success(
                pending_token_key=pending_token or "",
                user_id=user_id,
                ip=ip,
            )
        self.two_factor_repo.mark_as_used(valid_code.id)
        return True

