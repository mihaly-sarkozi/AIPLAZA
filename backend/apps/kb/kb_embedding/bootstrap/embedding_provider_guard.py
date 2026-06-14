from __future__ import annotations

from typing import Any

from core.kernel.config.config_loader import get_app_env
from core.kernel.config.environment import is_production_env


def validate_embedding_provider_runtime(settings: Any) -> None:
    provider = str(settings.embedding_provider or "local").strip().lower()
    env = get_app_env()
    allow_dummy = bool(getattr(settings, "embedding_allow_dummy", False))

    if is_production_env(env) and provider == "dummy":
        raise ValueError(
            "embedding_provider=dummy production környezetben tilos. Használj embedding_provider=local."
        )
    if provider == "dummy" and not allow_dummy:
        raise ValueError(
            "embedding_provider=dummy csak embedding_allow_dummy=true esetén engedélyezett (fejlesztői mód)."
        )
    if provider not in {"local", "openai", "dummy"}:
        raise ValueError("embedding_provider érvénytelen. Megengedett: local, openai, dummy.")


__all__ = ["validate_embedding_provider_runtime"]
