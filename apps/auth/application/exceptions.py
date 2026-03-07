# apps/auth/application/exceptions.py
# Auth application réteg kivételei (pl. email küldés sikertelen).
# A kivételek error_code-ot hordoznak, a presentation réteg ebből ad vissza i18n üzenetet.

from apps.core.i18n.messages import ErrorCode


class TwoFactorEmailError(Exception):
    """2FA kód email küldése sikertelen (SMTP hiba, konfiguráció, stb.). A router az error_code alapján ad i18n detail-t."""

    def __init__(self, message: str | None = None, error_code: ErrorCode | None = None):
        super().__init__(message or "Email send failed")
        self.error_code = error_code or ErrorCode.TWO_FACTOR_EMAIL_FAILED


class TwoFactorTooManyAttemptsError(Exception):
    """Túl sok sikertelen 2FA próbálkozás (pending token / user / IP). Új login step1 kell."""
    pass
