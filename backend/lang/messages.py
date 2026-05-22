# backend/lang/messages.py
# Feladat: Többnyelvű API/user-facing hibaüzeneteket és az ErrorCode enumot tartalmazza. Accept-Language alapján hu/en/es nyelvkódot normalizál, majd hibakódhoz tartozó üzenetet ad vissza fallbackkel a default magyar szövegre. Lokalizációs contract API detail és frontend megjelenítés számára.
# Sárközi Mihály - 2026.05.21

from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request

DEFAULT_LANG = "hu"


def lang_from_request(request: "Request") -> str:
    """Nyelv a kérés Accept-Language fejléce alapján (hu/en/es)."""
    accept = (getattr(request, "headers", None) or {}).get("Accept-Language") or ""
    first = accept.split(",")[0].strip().lower()[:2]
    return first if first in ("hu", "en", "es") else DEFAULT_LANG


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
    CREDENTIALS_PASSWORD_NOT_SET = "credentials_password_not_set"
    CREDENTIALS_ALREADY_SET = "credentials_already_set"
    NOT_DEMO_TENANT = "not_demo_tenant"
    DEMO_LOGIN_PASSWORD_SET = "demo_login_password_set"


# lang -> code (string) -> message
_MESSAGES: dict[str, dict[str, str]] = {
    "hu": {
        ErrorCode.TENANT_REQUIRED.value: "Használd a céges aldomaint az eléréshez (pl. demo.local, acme.local).",
        ErrorCode.ALREADY_LOGGED_IN.value: "Már be vagy jelentkezve. Először jelentkezz ki (POST /api/auth/logout), majd próbáld újra a belépést.",
        ErrorCode.TWO_FACTOR_EMAIL_FAILED.value: "A kétfaktoros kód emailt jelenleg nem tudtuk elküldeni. Ellenőrizd az SMTP beállításokat, vagy próbáld később.",
        ErrorCode.LOGIN_ERROR.value: "Belépési hiba. Próbáld később.",
        ErrorCode.INVALID_CREDENTIALS.value: "Hibás belépési adatok.",
        ErrorCode.TWO_FACTOR_TOO_MANY_ATTEMPTS.value: "Túl sok sikertelen 2FA kód. Jelentkezz be újra (1. lépés: email és jelszó).",
        ErrorCode.NO_REFRESH_TOKEN.value: "Nincs refresh token. A refresh token kizárólag HttpOnly cookie-ban fogadható (refresh_token cookie).",
        ErrorCode.INVALID_OR_REVOKED_REFRESH.value: "Érvénytelen vagy visszavont refresh token.",
        ErrorCode.PERMISSIONS_CHANGED.value: "Változás történt a jogosultságokban. Jelentkezz be újra.",
        ErrorCode.RE_2FA_REQUIRED.value: "Más eszközről vagy böngészőből történt a kérés. Jelentkezz be újra (email, jelszó és 2FA).",
        ErrorCode.AUTH_RATE_LIMIT.value: "Túl sok próbálkozás. Próbáld később újra.",
        ErrorCode.EMAIL_ALREADY_EXISTS.value: "Ez az email cím már használatban van.",
        ErrorCode.CURRENT_PASSWORD_WRONG.value: "A jelenlegi jelszó hibás. Nem sikerült módosítani.",
        ErrorCode.CREDENTIALS_PASSWORD_NOT_SET.value: "Még nincs beállítva saját jelszavad. Használd a „Jelszó beállítása” lehetőséget.",
        ErrorCode.CREDENTIALS_ALREADY_SET.value: "A jelszó már be van állítva. Használd a jelszó változtatást.",
        ErrorCode.NOT_DEMO_TENANT.value: "Ez a művelet csak demo környezetben érhető el.",
        ErrorCode.DEMO_LOGIN_PASSWORD_SET.value: "Már beállítottál jelszót. Lépj be emaillel és jelszóval; a gyors belépő link nem használható.",
    },
    "en": {
        ErrorCode.TENANT_REQUIRED.value: "Use the tenant subdomain to access (e.g. demo.local, acme.local).",
        ErrorCode.ALREADY_LOGGED_IN.value: "You are already logged in. Log out first (POST /api/auth/logout), then try again.",
        ErrorCode.TWO_FACTOR_EMAIL_FAILED.value: "We could not send the two-factor code email. Check SMTP settings or try again later.",
        ErrorCode.LOGIN_ERROR.value: "Login error. Please try again later.",
        ErrorCode.INVALID_CREDENTIALS.value: "Invalid credentials.",
        ErrorCode.TWO_FACTOR_TOO_MANY_ATTEMPTS.value: "Too many failed 2FA attempts. Please log in again from step 1 (email and password).",
        ErrorCode.NO_REFRESH_TOKEN.value: "No refresh token. Refresh token is accepted only in HttpOnly cookie (refresh_token cookie).",
        ErrorCode.INVALID_OR_REVOKED_REFRESH.value: "Invalid or revoked refresh token.",
        ErrorCode.PERMISSIONS_CHANGED.value: "Your permissions have changed. Please log in again.",
        ErrorCode.RE_2FA_REQUIRED.value: "Request from a different device or browser. Please log in again (email, password and 2FA).",
        ErrorCode.AUTH_RATE_LIMIT.value: "Too many attempts. Please try again later.",
        ErrorCode.EMAIL_ALREADY_EXISTS.value: "This email address is already in use.",
        ErrorCode.CURRENT_PASSWORD_WRONG.value: "Current password is incorrect. Change was not applied.",
        ErrorCode.CREDENTIALS_PASSWORD_NOT_SET.value: "You have not set a password yet. Use “Set password” instead.",
        ErrorCode.CREDENTIALS_ALREADY_SET.value: "A password is already set. Use change password.",
        ErrorCode.NOT_DEMO_TENANT.value: "This action is only available in the demo environment.",
        ErrorCode.DEMO_LOGIN_PASSWORD_SET.value: "You have set a password. Log in with email and password; the quick login link is no longer valid.",
    },
    "es": {
        ErrorCode.TENANT_REQUIRED.value: "Usa el subdominio del tenant para acceder (por ejemplo, demo.local, acme.local).",
        ErrorCode.ALREADY_LOGGED_IN.value: "Ya has iniciado sesión. Cierra la sesión primero (POST /api/auth/logout) y vuelve a intentarlo.",
        ErrorCode.TWO_FACTOR_EMAIL_FAILED.value: "No hemos podido enviar el correo con el código de dos factores. Revisa la configuración SMTP o inténtalo más tarde.",
        ErrorCode.LOGIN_ERROR.value: "Error de inicio de sesión. Inténtalo de nuevo más tarde.",
        ErrorCode.INVALID_CREDENTIALS.value: "Credenciales no válidas.",
        ErrorCode.TWO_FACTOR_TOO_MANY_ATTEMPTS.value: "Demasiados intentos fallidos de 2FA. Inicia sesión de nuevo desde el paso 1 (email y contraseña).",
        ErrorCode.NO_REFRESH_TOKEN.value: "No hay refresh token. El refresh token solo se acepta en una cookie HttpOnly (cookie refresh_token).",
        ErrorCode.INVALID_OR_REVOKED_REFRESH.value: "Refresh token no válido o revocado.",
        ErrorCode.PERMISSIONS_CHANGED.value: "Tus permisos han cambiado. Inicia sesión de nuevo.",
        ErrorCode.RE_2FA_REQUIRED.value: "La solicitud proviene de otro dispositivo o navegador. Inicia sesión de nuevo (email, contraseña y 2FA).",
        ErrorCode.AUTH_RATE_LIMIT.value: "Demasiados intentos. Inténtalo de nuevo más tarde.",
        ErrorCode.EMAIL_ALREADY_EXISTS.value: "Esta dirección de email ya está en uso.",
        ErrorCode.CURRENT_PASSWORD_WRONG.value: "La contraseña actual es incorrecta. No se aplicó el cambio.",
        ErrorCode.CREDENTIALS_PASSWORD_NOT_SET.value: "Todavía no has configurado una contraseña. Usa la opción \"Configurar contraseña\".",
        ErrorCode.CREDENTIALS_ALREADY_SET.value: "La contraseña ya está configurada. Usa el cambio de contraseña.",
        ErrorCode.NOT_DEMO_TENANT.value: "Esta acción solo está disponible en el entorno demo.",
        ErrorCode.DEMO_LOGIN_PASSWORD_SET.value: "Ya has configurado una contraseña. Inicia sesión con email y contraseña; el enlace de acceso rápido ya no es válido.",
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
