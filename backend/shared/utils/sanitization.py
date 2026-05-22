# backend/shared/utils/sanitization.py
# Feladat: Log és audit payloadok érzékeny mezőinek rekurzív maszkolását végzi. Jelszó-, token-, secret-, auth-, email- és 2FA jellegű értékeket biztonságos reprezentációra cserél, miközben a nem érzékeny struktúrát megtartja. Shared security-adjacent utility naplózási és audit rétegekhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
from typing import Any

REDACT_KEYS = frozenset({
    "password", "current_password", "new_password", "token", "refresh_token",
    "access_token", "pending_token", "two_factor_code", "code", "secret",
    "authorization", "cookie", "api_key", "jwt", "jwt_token", "api_secret",
    "prompt", "full_prompt", "system_prompt", "user_prompt", "context_text",
    "raw_content", "document_content", "text_content", "pii",
})

REDACT_KEY_PATTERN = re.compile(
    r"^(.*)(password|token|secret|key|auth|prompt|context_text|raw_content|document_content|text_content|pii)(.*)$",
    re.IGNORECASE,
)

TWO_FACTOR_KEY_PATTERN = re.compile(
    r"((2fa|two_factor|otp|verification).*code|code.*(2fa|two_factor|otp|verification))",
    re.IGNORECASE,
)


# Ez a függvény a(z) should_redact_key logikáját valósítja meg.
def _should_redact_key(key: str) -> bool:
    normalized = (key or "").strip().lower()
    return normalized in REDACT_KEYS or bool(REDACT_KEY_PATTERN.match(normalized))


# Ez a függvény a(z) mask_email logikáját valósítja meg.
def _mask_email(value: str) -> str:
    if "@" not in value:
        return "[REDACTED]"

    local, _, domain = value.partition("@")
    if not local or not domain:
        return "[REDACTED]"
    if len(local) < 4:
        return "[REDACTED]"

    visible_domain = domain if len(domain) < 5 else domain[-5:]
    hidden_domain_len = max(0, len(domain) - len(visible_domain))
    hidden_local_len = max(0, len(local) - 2)
    return f"{local[:2]}{'*' * hidden_local_len}@{'*' * hidden_domain_len}{visible_domain}"


# Ez a függvény a(z) mask_two_factor_numeric logikáját valósítja meg.
def _mask_two_factor_numeric(value: str) -> str:
    if len(value) <= 2:
        return value
    return f"{'*' * (len(value) - 2)}{value[-2:]}"


# Ez a függvény a(z) redact_value logikáját valósítja meg.
def _redact_value(key: str, value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, dict):
        return sanitize_log_data(value)

    if isinstance(value, list):
        return [_redact_value(key, item) for item in value]

    normalized_key = (key or "").lower()

    if "email" in normalized_key and isinstance(value, str):
        return _mask_email(value)

    if TWO_FACTOR_KEY_PATTERN.search(normalized_key):
        value_str = str(value)
        return _mask_two_factor_numeric(value_str) if value_str.isdigit() else "[REDACTED]"

    return "[REDACTED]"


def sanitize_log_data(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sensitive values are masked recursively for safe logging/audit persistence."""
    if details is None:
        return None

    sanitized: dict[str, Any] = {}

    for key, value in details.items():
        normalized = (key or "").lower()

        if _should_redact_key(key):
            sanitized[key] = _redact_value(key, value)
        elif "email" in normalized:
            if isinstance(value, str):
                sanitized[key] = _mask_email(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    _mask_email(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_log_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized

__all__ = ["sanitize_log_data"]
