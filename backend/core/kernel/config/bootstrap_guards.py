# backend/core/kernel/config/bootstrap_guards.py
# Feladat: A konfiguráció indításkori szerződését ellenőrzi környezetenként. Importkor nem akadályozza a modulbetöltést, hanem bootstrap/startup fázisban ad kontrollált hibát explicit env var vagy kritikus dependency hiány esetén. Core keretrendszer bootstrap guard.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

import os
from typing import Iterable

from core.kernel.config.environment import is_deployed_env, is_production_env, normalize_app_env


class ConfigBootstrapError(RuntimeError):
    pass


_DEPLOYED_EXPLICIT_ENV_VARS = (
    "APP_ENV",
    "DATABASE_URL",
    "JWT_SECRET",
    "JWT_ISSUER",
    "JWT_AUDIENCE",
    "FRONTEND_BASE_URL",
    "CORS_ORIGINS",
    "TRUSTED_HOSTS",
    "TENANT_BASE_DOMAIN",
    "REDIS_URL",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM_EMAIL",
)


def validate_config_bootstrap_contract(env: str | None = None) -> None:
    from core.kernel.config.config_loader import is_env_var_explicitly_set

    effective_env = normalize_app_env(env)

    if effective_env in {"local", "test"}:
        return

    if is_deployed_env(effective_env):
        missing = [
            name
            for name in _DEPLOYED_EXPLICIT_ENV_VARS
            if not _is_non_empty_env(name) or not is_env_var_explicitly_set(name)
        ]
        if missing:
            raise ConfigBootstrapError(
                f"{effective_env} környezetben explicit env varok kötelezők, nem import-time `.env` guard. "
                f"Hiányzó vagy üres változók: {', '.join(sorted(missing))}."
            )
        if is_production_env(effective_env) and not is_env_var_explicitly_set("APP_ENV"):
            raise ConfigBootstrapError("production környezetben APP_ENV=production explicit env var kötelező.")


def validate_settings(settings: object, env: str | None = None) -> None:
    validate_config_bootstrap_contract(env)
    if settings is None:
        raise ConfigBootstrapError("settings objektum hiányzik a bootstrap validációhoz.")


def _is_non_empty_env(name: str) -> bool:
    return bool(str(os.getenv(name) or "").strip())


def required_prod_env_vars() -> tuple[str, ...]:
    return _DEPLOYED_EXPLICIT_ENV_VARS


def validate_required_env_vars(names: Iterable[str]) -> list[str]:
    return [name for name in names if not _is_non_empty_env(name)]


__all__ = [
    "ConfigBootstrapError",
    "required_prod_env_vars",
    "validate_config_bootstrap_contract",
    "validate_required_env_vars",
    "validate_settings",
]
