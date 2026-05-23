# backend/core/modules/auth/domain/exceptions/two_factor_email_error.py
# Feladat: A 2FA kód email kézbesítési hibáját reprezentáló domain exception. ErrorCode értéket is hordoz, hogy a HTTP adapter lokalizált és egységes hibaválaszt tudjon adni. Auth domain exception a TwoFactorService és auth_router között.
# Sárközi Mihály - 2026.05.21

from lang.messages import ErrorCode


class TwoFactorEmailError(Exception):
    """2FA kód email küldése sikertelen."""

    # Kivétel létrehozása
    def __init__(self, message: str | None = None, error_code: ErrorCode = ErrorCode.TWO_FACTOR_EMAIL_FAILED):
        super().__init__(message or "Email send failed")
        self.error_code = error_code or ErrorCode.TWO_FACTOR_EMAIL_FAILED
