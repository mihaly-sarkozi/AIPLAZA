# backend/core/kernel/security/auth_policy_guards.py
# Feladat: Auth-hoz kapcsolódó indítási security policy guardokat futtat. JWT issuer/audience, 2FA, password policy és invite TTL szabályokat validál, de nem tartalmaz autentikációs flow logikát. Core startup security policy réteg az auth konfigurációhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.config.environment import is_production_env


class SecurityPolicyError(ValueError):
    """Akkor dob, ha indítási auth security policy validáció meghiúsul."""


def run_auth_policy_guards(settings: object, env: str) -> None:
    """Futtatja az összes auth-hoz kapcsolódó indítási policy guardot."""
    _validate_jwt_issuer_audience(settings, env)
    _validate_two_factor_policy(settings)
    _validate_password_policy_level(settings, env)
    _validate_invite_ttl(settings)


_MIN_ISSUER_AUDIENCE_LENGTH = 3
_MIN_2FA_CODE_EXPIRY_MIN = 1
_MAX_2FA_CODE_EXPIRY_MIN = 60
_VALID_PASSWORD_POLICY_LEVELS = {"basic", "standard", "high"}
_MAX_INVITE_TTL_HOURS = 168  # 7 nap


def _validate_jwt_issuer_audience(settings: object, env: str) -> None:
    issuer = (getattr(settings, "jwt_issuer", "AIPLAZA") or "AIPLAZA").strip()
    audience = (getattr(settings, "jwt_audience", "") or "").strip()

    if is_production_env(env):
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


def _validate_two_factor_policy(settings: object) -> None:
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


def _validate_password_policy_level(settings: object, env: str) -> None:
    level = (getattr(settings, "password_security_level", "standard") or "standard").strip().lower()

    if level not in _VALID_PASSWORD_POLICY_LEVELS:
        raise SecurityPolicyError(
            f"password_security_level érvénytelen érték: {level!r}. "
            f"Megengedett értékek: {sorted(_VALID_PASSWORD_POLICY_LEVELS)}"
        )

    if is_production_env(env) and level == "basic":
        raise SecurityPolicyError(
            "password_security_level='basic' production-ben nem engedélyezett. "
            "Legalább 'standard' szintet kell használni éles környezetben."
        )


def _validate_invite_ttl(settings: object) -> None:
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


__all__ = ["SecurityPolicyError", "run_auth_policy_guards"]
