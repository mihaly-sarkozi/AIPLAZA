# 2FA kód email küldése sikertelen kivétel
# 2026.03.07 - Sárközi Mihály
from lang.messages import ErrorCode


class TwoFactorEmailError(Exception):
    """2FA kód email küldése sikertelen."""

    # Kivétel létrehozása
    def __init__(self, message: str | None = None, error_code: ErrorCode = ErrorCode.TWO_FACTOR_EMAIL_FAILED):
        super().__init__(message or "Email send failed")
        self.error_code = error_code or ErrorCode.TWO_FACTOR_EMAIL_FAILED
