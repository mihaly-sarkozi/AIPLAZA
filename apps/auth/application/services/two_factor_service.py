# apps/auth/application/services/two_factor_service.py
# Kétfaktoros autentikáció szolgáltatás
# 2026.02.28 - Sárközi Mihály

import random
from datetime import datetime, timedelta, timezone
from apps.auth.ports import TwoFactorRepositoryInterface
from apps.auth.domain.two_factor_code import TwoFactorCode
from apps.auth.application.exceptions import TwoFactorEmailError
from apps.core.i18n.messages import ErrorCode
from apps.core.email.email_service import EmailService


class TwoFactorService:
    # 2FA kód generálás és validálás
    
    def __init__(
        self,
        two_factor_repo: TwoFactorRepositoryInterface,
        email_service: EmailService
    ):
        self.two_factor_repo = two_factor_repo
        self.email_service = email_service
        self.code_expiry_minutes = 10
    
    def generate_code(self) -> str:
        # 6 jegyű véletlenszerű kód generálása
        return f"{random.randint(100000, 999999)}"
    
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
    
    def verify_code(self, user_id: int, code: str) -> bool:
       
        # Ellenőrizzük a kódot
        valid_code = self.two_factor_repo.get_valid_code(user_id, code)
        
        if not valid_code:
            return False
        
        # Kód használatának jelölése
        self.two_factor_repo.mark_as_used(valid_code.id)
        
        return True

