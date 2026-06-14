from __future__ import annotations

from core.kernel.config.config_loader import settings


class QdrantConfigValidator:
    @staticmethod
    def is_configured() -> bool:
        return bool(str(settings.qdrant_url or "").strip())

    @staticmethod
    def validate_or_error_code() -> str | None:
        if not QdrantConfigValidator.is_configured():
            return "QDRANT_CONFIG_MISSING"
        return None


__all__ = ["QdrantConfigValidator"]
