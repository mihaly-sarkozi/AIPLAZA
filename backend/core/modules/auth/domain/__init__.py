# backend/core/modules/auth/domain/__init__.py
# Feladat: Az auth domain policy és helper API-k exportfelülete. Authorization, password policy és 2FA policy elemeket tesz elérhetővé, hogy use case-ek, router dependency-k és más modulok stabil domain importokat használjanak. Auth domain csomagbelépő, amely nem végez runtime assemblyt.
# Sárközi Mihály - 2026.05.21

from core.modules.auth.domain.authorization_policy import AuthorizationDecision, AuthorizationPolicy, normalize_values
from core.modules.auth.domain.password_policy import (
    AVAILABLE_PASSWORD_SECURITY_LEVELS,
    BASIC_PASSWORD_SECURITY_LEVEL,
    HIGH_PASSWORD_SECURITY_LEVEL,
    PasswordPolicy,
    STANDARD_PASSWORD_MAX_LEN,
    STANDARD_PASSWORD_MIN_LEN,
    STANDARD_PASSWORD_SECURITY_LEVEL,
    get_password_policy,
    validate_password_policy,
    validate_standard_password_policy,
)
from core.modules.auth.domain.two_factor_policy import (
    get_2fa_attempt_window_minutes,
    get_2fa_code_expiry_minutes,
    get_2fa_max_attempts,
)

__all__ = [
    "AVAILABLE_PASSWORD_SECURITY_LEVELS",
    "AuthorizationDecision",
    "AuthorizationPolicy",
    "BASIC_PASSWORD_SECURITY_LEVEL",
    "HIGH_PASSWORD_SECURITY_LEVEL",
    "PasswordPolicy",
    "STANDARD_PASSWORD_MAX_LEN",
    "STANDARD_PASSWORD_MIN_LEN",
    "STANDARD_PASSWORD_SECURITY_LEVEL",
    "get_2fa_attempt_window_minutes",
    "get_2fa_code_expiry_minutes",
    "get_2fa_max_attempts",
    "get_password_policy",
    "normalize_values",
    "validate_password_policy",
    "validate_standard_password_policy",
]
