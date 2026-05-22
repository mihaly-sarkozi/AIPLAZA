# backend/core/kernel/security/jwt_guards.py
# Feladat: JWT secret jelenlétét, formátumát és nem-local környezetben az env alapú explicit beállítást validálja. Staging/prod környezetben megköveteli a környezeti JWT_SECRET használatát, megfelelő hosszt és minimális entrópiát. Core startup security guard a token aláírási titokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os

from core.kernel.security.errors import SecurityConfigError

_JWT_SECRET_ENV_REQUIRED_ENVS = {"staging", "production"}


def validate_jwt_config_presence_and_format(settings: object, env: str) -> str:
    secret = getattr(settings, "jwt_secret", "")
    normalized_secret = str(secret or "").strip()
    if not normalized_secret:
        raise SecurityConfigError(
            "jwt_secret nincs beállítva. "
            "Generálj egyet: openssl rand -hex 64"
        )
    if len(normalized_secret) < 32:
        raise SecurityConfigError(
            f"jwt_secret túl rövid ({len(normalized_secret)} karakter); minimum 32 szükséges. "
            "Generálj egyet: openssl rand -hex 64"
        )

    if env not in _JWT_SECRET_ENV_REQUIRED_ENVS:
        return normalized_secret

    env_secret = (os.getenv("JWT_SECRET") or "").strip()
    if not env_secret:
        raise SecurityConfigError(
            f"APP_ENV={env} környezetben a JWT_SECRET környezeti változó megadása kötelező. "
            "Generálj egyet: openssl rand -hex 64"
        )
    if len(env_secret) < 64:
        raise SecurityConfigError(
            f"APP_ENV={env} JWT_SECRET legalább 64 karakter hosszú kell legyen "
            f"(jelenlegi: {len(env_secret)} karakter). "
            "Generálj egyet: openssl rand -hex 64"
        )
    return env_secret


def validate_jwt_secret_strength(secret: str, env: str) -> None:
    if env not in _JWT_SECRET_ENV_REQUIRED_ENVS:
        return
    if len(set(secret)) < 16:
        raise SecurityConfigError(
            f"APP_ENV={env} JWT_SECRET entrópiája elégtelen (túl sok ismétlődő karakter). "
            "Generálj egyet: openssl rand -hex 64"
        )


__all__ = ["validate_jwt_config_presence_and_format", "validate_jwt_secret_strength"]
