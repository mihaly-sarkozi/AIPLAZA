from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALLOWED_ENVS = {"dev", "prod"}


def _resolve_env_path() -> Path:
    candidates = (
        _PROJECT_ROOT / ".env",
        _PROJECT_ROOT.parent / ".env",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


@lru_cache(maxsize=1)
def load_project_env() -> Path:
    env_path = _resolve_env_path()
    load_dotenv(env_path)
    return env_path


def get_app_env() -> str:
    load_project_env()
    env = (os.getenv("APP_ENV") or "dev").strip().lower()
    if env not in _ALLOWED_ENVS:
        allowed = ", ".join(sorted(_ALLOWED_ENVS))
        raise ValueError(f"APP_ENV csak a következők egyike lehet: {allowed}. Kapott érték: {env!r}")
    return env


__all__ = ["get_app_env", "load_project_env"]
