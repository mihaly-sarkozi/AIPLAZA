"""Domain szintű auth policy validátorok.

Felelősség: az auth domain belső konzisztenciájának és policy-jának ellenőrzése:
  - JWT issuer/audience szerződés
  - 2FA konfiguráció konzisztencia
  - Jelszó policy szint érvényessége
  - Invite token TTL ésszerűsége

Ezek POLICY szintű ellenőrzések (mit követel a domain), nem infrastruktúra szintűek
(hogyan kényszeríti ki a rendszer). Az infrastruktúra / kernel szintű guard-ok a
core/kernel/security/startup_guards.py fájlban találhatók.

Bármilyen hiba esetén SecurityPolicyError-t dob egyértelmű, cselekvésorientált üzenettel.
"""
from __future__ import annotations


class SecurityPolicyError(ValueError):
    """Akkor dob, ha domain szintű auth policy validáció meghiúsul."""


# ---------------------------------------------------------------------------
# JWT issuer/audience guard
# ---------------------------------------------------------------------------

_MIN_ISSUER_AUDIENCE_LENGTH = 3


def validate_jwt_issuer_audience(settings: object, env: str) -> None:
    """JWT issuer és audience konzisztenciájának ellenőrzése.

    - jwt_issuer: beállításból (alapértelmezés: AIPLAZA); prod-ban kötelező,
      legalább 3 karakter.
    - jwt_audience: dev-ben opcionális; prod-ban kötelező, legalább 3 karakter,
      és nem lehet megegyezni az issuerrel.
    """
    issuer = (getattr(settings, "jwt_issuer", "AIPLAZA") or "AIPLAZA").strip()
    audience = (getattr(settings, "jwt_audience", "") or "").strip()

    if env == "prod":
        if len(issuer) < _MIN_ISSUER_AUDIENCE_LENGTH:
            raise SecurityPolicyError(
                f"jwt_issuer túl rövid ({issuer!r}). "
                f"Legalább {_MIN_ISSUER_AUDIENCE_LENGTH} karakteres azonosítót adj meg."
            )
        if not audience:
            raise SecurityPolicyError(
                "jwt_audience production-ben kötelező. "
                "Adj meg egy egyértelmű API/resource azonosítót (pl. 'https://api.example.com')."
            )

    if not audience:
        return

    if len(audience) < _MIN_ISSUER_AUDIENCE_LENGTH:
        raise SecurityPolicyError(
            f"jwt_audience túl rövid ({audience!r}). "
            f"Legalább {_MIN_ISSUER_AUDIENCE_LENGTH} karakteres, érdemi azonosítót adj meg "
            "(pl. 'api.example.com')."
        )

    if audience == issuer:
        raise SecurityPolicyError(
            f"jwt_audience ({audience!r}) nem lehet ugyanaz mint a jwt_issuer ({issuer!r}). "
            "Használj különböző azonosítókat a kiadónak és a célközönségnek."
        )


# ---------------------------------------------------------------------------
# 2FA policy guard
# ---------------------------------------------------------------------------

_MIN_2FA_CODE_EXPIRY_MIN = 1
_MAX_2FA_CODE_EXPIRY_MIN = 60


def validate_two_factor_policy(settings: object) -> None:
    """2FA konfiguráció belső konzisztenciájának ellenőrzése.

    - Minden értéknek pozitívnak kell lennie.
    - A kód lejárati ideje rövidebb kell legyen a kísérlet ablaknál.
    - A kód lejárata ésszerű határok között kell legyen.
    """
    try:
        max_attempts = int(getattr(settings, "two_fa_max_attempts", 5))
        window_minutes = int(getattr(settings, "two_fa_attempt_window_minutes", 15))
        code_expiry = int(getattr(settings, "two_fa_code_expiry_minutes", 10))
    except (TypeError, ValueError) as exc:
        raise SecurityPolicyError(f"Érvénytelen 2FA konfiguráció: {exc}") from exc

    if max_attempts <= 0:
        raise SecurityPolicyError(
            f"two_fa_max_attempts értéke {max_attempts}, de pozitívnak kell lennie."
        )
    if window_minutes <= 0:
        raise SecurityPolicyError(
            f"two_fa_attempt_window_minutes értéke {window_minutes}, de pozitívnak kell lennie."
        )
    if code_expiry <= 0:
        raise SecurityPolicyError(
            f"two_fa_code_expiry_minutes értéke {code_expiry}, de pozitívnak kell lennie."
        )

    if code_expiry > _MAX_2FA_CODE_EXPIRY_MIN:
        raise SecurityPolicyError(
            f"two_fa_code_expiry_minutes={code_expiry} perc indokolatlanul hosszú "
            f"(ajánlott maximum: {_MAX_2FA_CODE_EXPIRY_MIN} perc). "
            "A 2FA kód lejárata legyen rövid, hogy csökkentse a phishing kockázatot."
        )

    if code_expiry >= window_minutes:
        raise SecurityPolicyError(
            f"two_fa_code_expiry_minutes ({code_expiry} perc) nem lehet >= "
            f"two_fa_attempt_window_minutes ({window_minutes} perc). "
            "A kód lejáratának rövidebbnek kell lennie a kísérlet ablaktól, "
            "hogy lejárt kóddal ne lehessen újra próbálkozni."
        )


# ---------------------------------------------------------------------------
# Password policy guard
# ---------------------------------------------------------------------------

_VALID_PASSWORD_POLICY_LEVELS = {"basic", "standard", "high"}


def validate_password_policy_level(settings: object, env: str) -> None:
    """Jelszó policy szintjének ellenőrzése.

    - Csak "basic", "standard" vagy "high" elfogadott.
    - Production-ben "basic" nem engedélyezett (elégtelen erősség).
    """
    level = (getattr(settings, "password_security_level", "standard") or "standard").strip().lower()

    if level not in _VALID_PASSWORD_POLICY_LEVELS:
        raise SecurityPolicyError(
            f"password_security_level érvénytelen érték: {level!r}. "
            f"Megengedett értékek: {sorted(_VALID_PASSWORD_POLICY_LEVELS)}"
        )

    if env == "prod" and level == "basic":
        raise SecurityPolicyError(
            "password_security_level='basic' production-ben nem engedélyezett. "
            "Legalább 'standard' szintet kell használni éles környezetben."
        )


# ---------------------------------------------------------------------------
# Invite token TTL guard
# ---------------------------------------------------------------------------

_MAX_INVITE_TTL_HOURS = 168  # 7 nap


def validate_invite_ttl(settings: object) -> None:
    """Invite token TTL ésszerűségének ellenőrzése.

    - Pozitívnak kell lennie.
    - Maximum 7 nap (168 óra) a biztonságos felső határ.
    """
    try:
        invite_ttl = int(getattr(settings, "invite_ttl_hours", 4))
    except (TypeError, ValueError) as exc:
        raise SecurityPolicyError(f"Érvénytelen invite_ttl_hours: {exc}") from exc

    if invite_ttl <= 0:
        raise SecurityPolicyError(
            f"invite_ttl_hours értéke {invite_ttl}, de pozitívnak kell lennie."
        )
    if invite_ttl > _MAX_INVITE_TTL_HOURS:
        raise SecurityPolicyError(
            f"invite_ttl_hours={invite_ttl} óra indokolatlanul hosszú "
            f"(ajánlott maximum: {_MAX_INVITE_TTL_HOURS} óra = 7 nap). "
            "Rövid életű invite linkek csökkentik az elfogás kockázatát."
        )


# ---------------------------------------------------------------------------
# Összefoglaló belépési pont
# ---------------------------------------------------------------------------


def run_auth_policy_guards(settings: object, env: str) -> None:
    """Futtatja az összes domain szintű auth policy guard-ot.

    Az alkalmazás indulása előtt hívd meg ezt a függvényt, a kernel guard-ok után.
    Bármilyen hiba esetén SecurityPolicyError-t dob egyértelmű üzenettel.
    """
    validate_jwt_issuer_audience(settings, env)
    run_non_jwt_auth_policy_guards(settings, env)


def run_non_jwt_auth_policy_guards(settings: object, env: str) -> None:
    """A nem-JWT auth policy guard-ok külön futtatható belépési pontja."""
    validate_two_factor_policy(settings)
    validate_password_policy_level(settings, env)
    validate_invite_ttl(settings)


__all__ = [
    "SecurityPolicyError",
    "run_auth_policy_guards",
    "run_non_jwt_auth_policy_guards",
    "validate_invite_ttl",
    "validate_jwt_issuer_audience",
    "validate_password_policy_level",
    "validate_two_factor_policy",
]
