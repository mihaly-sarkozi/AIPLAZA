# backend/shared/validation/password.py
# Feladat: Közös jelszóerősségi policy szinteket és validációt definiál. Basic, standard és high szabályokat tartalmaz, a settings olvasását lazy módon végzi, hogy shared validációként core, admin és app rétegek is használhassák. Kanonikus password validation utility.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
from dataclasses import dataclass

BASIC_PASSWORD_SECURITY_LEVEL = "basic"
STANDARD_PASSWORD_SECURITY_LEVEL = "standard"
HIGH_PASSWORD_SECURITY_LEVEL = "high"

AVAILABLE_PASSWORD_SECURITY_LEVELS = (
    BASIC_PASSWORD_SECURITY_LEVEL,
    STANDARD_PASSWORD_SECURITY_LEVEL,
    HIGH_PASSWORD_SECURITY_LEVEL,
)


@dataclass(frozen=True)
class PasswordPolicy:
    min_len: int
    max_len: int
    require_lower: bool
    require_upper: bool
    require_digit: bool
    require_special: bool


PASSWORD_POLICIES: dict[str, PasswordPolicy] = {
    BASIC_PASSWORD_SECURITY_LEVEL: PasswordPolicy(
        min_len=6,
        max_len=128,
        require_lower=False,
        require_upper=False,
        require_digit=False,
        require_special=False,
    ),
    STANDARD_PASSWORD_SECURITY_LEVEL: PasswordPolicy(
        min_len=6,
        max_len=128,
        require_lower=True,
        require_upper=True,
        require_digit=True,
        require_special=False,
    ),
    HIGH_PASSWORD_SECURITY_LEVEL: PasswordPolicy(
        min_len=10,
        max_len=128,
        require_lower=True,
        require_upper=True,
        require_digit=True,
        require_special=True,
    ),
}

STANDARD_PASSWORD_MIN_LEN = PASSWORD_POLICIES[STANDARD_PASSWORD_SECURITY_LEVEL].min_len
STANDARD_PASSWORD_MAX_LEN = PASSWORD_POLICIES[STANDARD_PASSWORD_SECURITY_LEVEL].max_len


def get_password_policy(security_level: str | None = None) -> PasswordPolicy:
    if security_level is None:
        from core.kernel.config.config_loader import settings  # lazy: avoids config load at import time

        security_level = getattr(settings, "password_security_level", None)
    level = (security_level or STANDARD_PASSWORD_SECURITY_LEVEL).strip().lower()
    try:
        return PASSWORD_POLICIES[level]
    except KeyError as exc:
        supported = ", ".join(AVAILABLE_PASSWORD_SECURITY_LEVELS)
        raise ValueError(f"Ismeretlen jelszo biztonsagi szint: {level}. Tamogatott: {supported}.") from exc


def validate_password_policy(
    password: str | None,
    *,
    security_level: str | None = None,
) -> tuple[bool, str]:
    if not password or not isinstance(password, str):
        return False, "Jelszó megadása kötelező."

    policy = get_password_policy(security_level)
    if len(password) < policy.min_len:
        return False, f"A jelszónak legalább {policy.min_len} karakter hosszúnak kell lennie."
    if len(password) > policy.max_len:
        return False, f"A jelszó legfeljebb {policy.max_len} karakter lehet."
    if policy.require_lower and not re.search(r"[a-z]", password):
        return False, "A jelszónak tartalmaznia kell legalább egy kisbetűt."
    if policy.require_upper and not re.search(r"[A-Z]", password):
        return False, "A jelszónak tartalmaznia kell legalább egy nagybetűt."
    if policy.require_digit and not re.search(r"\d", password):
        return False, "A jelszónak tartalmaznia kell legalább egy számot."
    if policy.require_special and not re.search(r"[^A-Za-z0-9]", password):
        return False, "A jelszónak tartalmaznia kell legalább egy speciális karaktert."
    return True, ""


def validate_standard_password_policy(password: str | None) -> tuple[bool, str]:
    return validate_password_policy(password, security_level=STANDARD_PASSWORD_SECURITY_LEVEL)

PASSWORD_MIN_LEN = STANDARD_PASSWORD_MIN_LEN
PASSWORD_MAX_LEN = STANDARD_PASSWORD_MAX_LEN


def validate_password_strength(
    password: str | None,
    *,
    security_level: str | None = None,
) -> tuple[bool, str]:
    """Visszafele kompatibilis alias a közös jelszópolicy validációhoz."""
    return validate_password_policy(password, security_level=security_level)


__all__ = [
    "AVAILABLE_PASSWORD_SECURITY_LEVELS",
    "BASIC_PASSWORD_SECURITY_LEVEL",
    "HIGH_PASSWORD_SECURITY_LEVEL",
    "PASSWORD_MAX_LEN",
    "PASSWORD_MIN_LEN",
    "PASSWORD_POLICIES",
    "PasswordPolicy",
    "STANDARD_PASSWORD_MAX_LEN",
    "STANDARD_PASSWORD_MIN_LEN",
    "STANDARD_PASSWORD_SECURITY_LEVEL",
    "get_password_policy",
    "validate_password_policy",
    "validate_password_strength",
    "validate_standard_password_policy",
]
