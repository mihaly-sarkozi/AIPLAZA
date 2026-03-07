# apps/core/i18n/messages.py
# Hibakódok és felhasználói üzenetek többnyelvűen. API detail / frontend üzenetekhez.
# Használat: get_message(ErrorCode.TENANT_REQUIRED, lang="hu") -> "Használd a céges aldomaint..."

from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request

DEFAULT_LANG = "hu"


def lang_from_request(request: "Request") -> str:
    """Nyelv a kérés Accept-Language fejléce alapján (hu/en)."""
    accept = (getattr(request, "headers", None) or {}).get("Accept-Language") or ""
    first = accept.split(",")[0].strip().lower()[:2]
    return first if first in ("hu", "en") else DEFAULT_LANG


class ErrorCode(str, Enum):
    """API / alkalmazás hibakódok; a router ezt adja vissza, a kliens a kód alapján jeleníthet meg saját szöveget."""
    # Auth / login
    TENANT_REQUIRED = "tenant_required"
    ALREADY_LOGGED_IN = "already_logged_in"
    TWO_FACTOR_EMAIL_FAILED = "two_factor_email_failed"
    LOGIN_ERROR = "login_error"
    INVALID_CREDENTIALS = "invalid_credentials"
    TWO_FACTOR_TOO_MANY_ATTEMPTS = "two_factor_too_many_attempts"
    NO_REFRESH_TOKEN = "no_refresh_token"
    INVALID_OR_REVOKED_REFRESH = "invalid_or_revoked_refresh"
    PERMISSIONS_CHANGED = "permissions_changed"
    RE_2FA_REQUIRED = "re_2fa_required"
    AUTH_RATE_LIMIT = "auth_rate_limit"
    # Users
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    CURRENT_PASSWORD_WRONG = "current_password_wrong"


# lang -> code (string) -> message
_MESSAGES: dict[str, dict[str, str]] = {
    "hu": {
        ErrorCode.TENANT_REQUIRED.value: "Használd a céges aldomaint az eléréshez (pl. demo.local, acme.local).",
        ErrorCode.ALREADY_LOGGED_IN.value: "Már be vagy jelentkezve. Először jelentkezz ki (POST /api/auth/logout), majd próbáld újra a belépést.",
        ErrorCode.TWO_FACTOR_EMAIL_FAILED.value: "A kétfaktoros kód emailt jelenleg nem tudtuk elküldeni. Ellenőrizd az SMTP beállításokat, vagy próbáld később.",
        ErrorCode.LOGIN_ERROR.value: "Belépési hiba. Próbáld később.",
        ErrorCode.INVALID_CREDENTIALS.value: "Hibás belépési adatok.",
        ErrorCode.TWO_FACTOR_TOO_MANY_ATTEMPTS.value: "Túl sok sikertelen 2FA kód. Jelentkezz be újra (1. lépés: email és jelszó).",
        ErrorCode.NO_REFRESH_TOKEN.value: "Nincs refresh token (küldd cookie-ban refresh_token vagy X-Refresh-Token headerben).",
        ErrorCode.INVALID_OR_REVOKED_REFRESH.value: "Érvénytelen vagy visszavont refresh token.",
        ErrorCode.PERMISSIONS_CHANGED.value: "Változás történt a jogosultságokban. Jelentkezz be újra.",
        ErrorCode.RE_2FA_REQUIRED.value: "Más eszközről vagy böngészőből történt a kérés. Jelentkezz be újra (email, jelszó és 2FA).",
        ErrorCode.AUTH_RATE_LIMIT.value: "Túl sok próbálkozás. Próbáld később újra.",
        ErrorCode.EMAIL_ALREADY_EXISTS.value: "Ez az email cím már használatban van.",
        ErrorCode.CURRENT_PASSWORD_WRONG.value: "A jelenlegi jelszó hibás. Nem sikerült módosítani.",
    },
    "en": {
        ErrorCode.TENANT_REQUIRED.value: "Use the tenant subdomain to access (e.g. demo.local, acme.local).",
        ErrorCode.ALREADY_LOGGED_IN.value: "You are already logged in. Log out first (POST /api/auth/logout), then try again.",
        ErrorCode.TWO_FACTOR_EMAIL_FAILED.value: "We could not send the two-factor code email. Check SMTP settings or try again later.",
        ErrorCode.LOGIN_ERROR.value: "Login error. Please try again later.",
        ErrorCode.INVALID_CREDENTIALS.value: "Invalid credentials.",
        ErrorCode.TWO_FACTOR_TOO_MANY_ATTEMPTS.value: "Too many failed 2FA attempts. Please log in again from step 1 (email and password).",
        ErrorCode.NO_REFRESH_TOKEN.value: "No refresh token (send refresh_token cookie or X-Refresh-Token header).",
        ErrorCode.INVALID_OR_REVOKED_REFRESH.value: "Invalid or revoked refresh token.",
        ErrorCode.PERMISSIONS_CHANGED.value: "Your permissions have changed. Please log in again.",
        ErrorCode.RE_2FA_REQUIRED.value: "Request from a different device or browser. Please log in again (email, password and 2FA).",
        ErrorCode.AUTH_RATE_LIMIT.value: "Too many attempts. Please try again later.",
        ErrorCode.EMAIL_ALREADY_EXISTS.value: "This email address is already in use.",
        ErrorCode.CURRENT_PASSWORD_WRONG.value: "Current password is incorrect. Change was not applied.",
    },
}


def get_message(code: ErrorCode | str, lang: Optional[str] = None) -> str:
    """
    Hibakódhoz tartozó felhasználói üzenet a kért nyelven.
    Ha nincs a nyelv, visszaadja a DEFAULT_LANG üzenetét; ha a kód nincs meg, a kód stringje.
    """
    lang = lang or DEFAULT_LANG
    if lang not in _MESSAGES:
        lang = DEFAULT_LANG
    code_key = code.value if isinstance(code, ErrorCode) else code
    messages = _MESSAGES[lang]
    if code_key in messages:
        return messages[code_key]
    if DEFAULT_LANG in _MESSAGES and code_key in _MESSAGES[DEFAULT_LANG]:
        return _MESSAGES[DEFAULT_LANG][code_key]
    return str(code_key)
