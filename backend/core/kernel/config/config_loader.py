# backend/core/kernel/config/config_loader.py
# Feladat: Opcionálisan betölti a `.env` és `.env.local` fájlokat, validálja az APP_ENV értékét, és lazy settings hozzáférést ad. Importkor nem dob `.env` hiány miatt; a környezetenként kötelező konfigurációt bootstrap/startup guard ellenőrzi kontrollált hibával. Core keretrendszer-elem, mert az alkalmazás konfigurációs betöltési szerződését adja.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from dotenv import load_dotenv

from core.kernel.config.base import AppSettings
from core.kernel.config.environment import normalize_app_env

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_PATH = _PROJECT_ROOT / ".env"
_ENV_LOCAL_PATH = _PROJECT_ROOT / ".env.local"
_INITIAL_ENV_KEYS = frozenset(os.environ.keys())
_LOADED_ENV_FILES: list[Path] = []


def _load_env_files() -> None:
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
        _LOADED_ENV_FILES.append(_ENV_PATH)
    try:
        effective_env = normalize_app_env(os.getenv("APP_ENV") or "local")
    except ValueError:
        effective_env = "local"
    if _ENV_LOCAL_PATH.exists() and effective_env != "production":
        load_dotenv(_ENV_LOCAL_PATH, override=True)
        _LOADED_ENV_FILES.append(_ENV_LOCAL_PATH)


_load_env_files()


def get_app_env() -> str:
    return normalize_app_env()


def get_env_file_status() -> dict[str, object]:
    return {
        "project_root": _PROJECT_ROOT,
        "env_path": _ENV_PATH,
        "env_exists": _ENV_PATH.exists(),
        "env_local_path": _ENV_LOCAL_PATH,
        "env_local_exists": _ENV_LOCAL_PATH.exists(),
        "loaded_env_files": tuple(_LOADED_ENV_FILES),
    }


def is_env_var_explicitly_set(name: str) -> bool:
    wanted = str(name or "").strip().upper()
    return any(key.upper() == wanted for key in _INITIAL_ENV_KEYS)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    from core.kernel.config.bootstrap_guards import ConfigBootstrapError

    try:
        return AppSettings()
    except ValidationError as exc:
        raise ConfigBootstrapError(
            "Érvénytelen vagy hiányos alkalmazás konfiguráció. "
            "Importkor nincs `.env` guard; app bootstrapkor a validate_settings() "
            "ad környezetfüggő, strukturált hibát."
        ) from exc


class _LazySettings:
    def _wrapped(self) -> AppSettings:
        return get_settings()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._wrapped(), name, value)

    def __repr__(self) -> str:
        return repr(self._wrapped())


settings = _LazySettings()


__all__ = [
    "get_app_env",
    "get_env_file_status",
    "get_settings",
    "is_env_var_explicitly_set",
    "settings",
]
