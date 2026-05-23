# backend/shared/validation/__init__.py
# Feladat: A shared validation csomag publikus exportfelülete. Email és password validációs helper függvényeket, hosszkorlátokat és policy contractokat ad tovább core, admin és app rétegeknek. Általános validációs utility belépési pont.
# Sárközi Mihály - 2026.05.21

from shared.validation.email import is_valid_email, EMAIL_MAX_LEN
from shared.validation.password import (
    AVAILABLE_PASSWORD_SECURITY_LEVELS,
    PASSWORD_MAX_LEN,
    PASSWORD_MIN_LEN,
    PASSWORD_POLICIES,
    PasswordPolicy,
    STANDARD_PASSWORD_MAX_LEN,
    STANDARD_PASSWORD_MIN_LEN,
    STANDARD_PASSWORD_SECURITY_LEVEL,
    get_password_policy,
    validate_password_policy,
    validate_password_strength,
    validate_standard_password_policy,
)

__all__ = [
    "AVAILABLE_PASSWORD_SECURITY_LEVELS",
    "EMAIL_MAX_LEN",
    "PASSWORD_MAX_LEN",
    "PASSWORD_MIN_LEN",
    "PASSWORD_POLICIES",
    "PasswordPolicy",
    "STANDARD_PASSWORD_MAX_LEN",
    "STANDARD_PASSWORD_MIN_LEN",
    "STANDARD_PASSWORD_SECURITY_LEVEL",
    "get_password_policy",
    "is_valid_email",
    "validate_password_policy",
    "validate_password_strength",
    "validate_standard_password_policy",
]
