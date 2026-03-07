# apps/audit/sanitization.py
# Audit sanitization: érzékeny adat ne kerüljön audit logba (jelszó, token, teljes email opcionálisan).
# A details dict kulcsai alapján redaktálunk; a log írás előtt hívjuk (pl. event channel worker).
# Biztonság: adatvédelem, compliance; üzleti logika változatlan.

from __future__ import annotations

import re
from typing import Any

# Kulcsok (case-insensitive), amelyek értékét kivágjuk vagy hash-eljük
REDACT_KEYS = frozenset({
    "password", "current_password", "new_password", "token", "refresh_token",
    "access_token", "pending_token", "two_factor_code", "code", "secret",
    "authorization", "cookie", "api_key", "jwt",
})
# Ha a kulcs ezeket tartalmazza (regex), redact
REDACT_KEY_PATTERN = re.compile(
    r"^(.*)(password|token|secret|key|auth)(.*)$",
    re.IGNORECASE,
)
# Email: opcionálisan csak domain (user@ → ***@domain) vagy teljes redact
MASK_EMAIL = True  # True = ***@domain.com; False = ne redactáljuk az email mezőt


def _redact_value(_key: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and len(value) > 0:
        return "[REDACTED]"
    if isinstance(value, dict):
        return sanitize_details(value)
    if isinstance(value, list):
        return [_redact_value(_key, v) for v in value]
    return value


def _should_redact_key(key: str) -> bool:
    k = (key or "").strip().lower()
    if k in REDACT_KEYS:
        return True
    if REDACT_KEY_PATTERN.match(k):
        return True
    return False


def _mask_email_if_needed(key: str, value: Any) -> Any:
    if not MASK_EMAIL or not isinstance(value, str):
        return value
    k = (key or "").lower()
    if "email" not in k:
        return value
    # ***@domain.com
    if "@" in value:
        local, _, domain = value.partition("@")
        return f"***@{domain}" if domain else "[REDACTED]"
    return "[REDACTED]"


def sanitize_details(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Érzékeny mezők kivágása vagy maszkolása.
    Vissza: új dict (eredeti nem módosul); None → None.
    """
    if details is None:
        return None
    out: dict[str, Any] = {}
    for k, v in details.items():
        if _should_redact_key(k):
            out[k] = _redact_value(k, v)
        elif "email" in (k or "").lower() and MASK_EMAIL:
            out[k] = _mask_email_if_needed(k, v)
        elif isinstance(v, dict):
            out[k] = sanitize_details(v)
        elif isinstance(v, list):
            out[k] = [sanitize_details(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out
