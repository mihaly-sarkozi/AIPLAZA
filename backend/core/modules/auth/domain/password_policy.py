# backend/core/modules/auth/domain/password_policy.py
# Feladat: Visszafele kompatibilis auth domain export a közös jelszópolicy validációhoz. A kanonikus implementáció a shared.validation.password modulban van, innen a régi auth importútvonalak változatlanul működnek. Kompatibilitási shim jelszóbeállítási és meghívási folyamatokhoz.
# Sárközi Mihály - 2026.05.21

from shared.validation.password import (
    AVAILABLE_PASSWORD_SECURITY_LEVELS,
    BASIC_PASSWORD_SECURITY_LEVEL,
    HIGH_PASSWORD_SECURITY_LEVEL,
    PASSWORD_POLICIES,
    PasswordPolicy,
    STANDARD_PASSWORD_MAX_LEN,
    STANDARD_PASSWORD_MIN_LEN,
    STANDARD_PASSWORD_SECURITY_LEVEL,
    get_password_policy,
    validate_password_policy,
    validate_standard_password_policy,
)


__all__ = [
    "AVAILABLE_PASSWORD_SECURITY_LEVELS",
    "BASIC_PASSWORD_SECURITY_LEVEL",
    "HIGH_PASSWORD_SECURITY_LEVEL",
    "PasswordPolicy",
    "STANDARD_PASSWORD_MAX_LEN",
    "STANDARD_PASSWORD_MIN_LEN",
    "STANDARD_PASSWORD_SECURITY_LEVEL",
    "get_password_policy",
    "validate_password_policy",
    "validate_standard_password_policy",
]
