# Ez a fájl több modul által közösen használt backend segédlogikát tartalmaz.
from core.platform.auth.password_policy import (
    get_password_policy,
    validate_password_policy,
)

PASSWORD_MIN_LEN = get_password_policy().min_len
PASSWORD_MAX_LEN = get_password_policy().max_len


def validate_password_strength(
    password: str | None,
    *,
    security_level: str | None = None,
) -> tuple[bool, str]:
    """Visszafele kompatibilis alias a kernel jelszopolicy validaciohoz."""
    return validate_password_policy(password, security_level=security_level)
