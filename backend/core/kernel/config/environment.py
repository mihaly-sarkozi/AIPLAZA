from __future__ import annotations

import os

_ENV_ALIASES = {
    "dev": "local",
    "prod": "production",
}
_ALLOWED_ENVS = {"local", "test", "staging", "production"}


def normalize_app_env(value: str | None = None) -> str:
    env = str(value if value is not None else os.getenv("APP_ENV", "local")).strip().lower()
    env = _ENV_ALIASES.get(env, env)
    if env not in _ALLOWED_ENVS:
        allowed = ", ".join(sorted(_ALLOWED_ENVS))
        raise ValueError(f"APP_ENV csak a következők egyike lehet: {allowed}. Kapott érték: {env!r}")
    return env


def is_local_env(env: str | None = None) -> bool:
    return normalize_app_env(env) == "local"


def is_test_env(env: str | None = None) -> bool:
    return normalize_app_env(env) == "test"


def is_staging_env(env: str | None = None) -> bool:
    return normalize_app_env(env) == "staging"


def is_production_env(env: str | None = None) -> bool:
    return normalize_app_env(env) == "production"


def is_deployed_env(env: str | None = None) -> bool:
    return normalize_app_env(env) in {"staging", "production"}


__all__ = [
    "is_deployed_env",
    "is_local_env",
    "is_production_env",
    "is_staging_env",
    "is_test_env",
    "normalize_app_env",
]
