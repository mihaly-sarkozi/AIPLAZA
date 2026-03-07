# apps/core/validation/email.py
# Email formátum és hossz validáció (központi; audit/regisztráció/bejelentkezés).

import re

# RFC 5322 egyszerűsített: local@domain, max hossz
EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)
EMAIL_MAX_LEN = 255


def is_valid_email(value: str | None) -> bool:
    """Érvényes email formátum és hossz."""
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    if len(s) > EMAIL_MAX_LEN or len(s) < 3:
        return False
    return bool(EMAIL_PATTERN.match(s))
